import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import GpuLease, JobStatus, JobStep, SessionJob
from app.services.jobs import has_audio, has_transcription, update_job_status

logger = logging.getLogger(__name__)


class JobRunner:
    """Orchestrateur simple — pas de queue distribuée complexe."""

    def __init__(self, db_factory, pipeline):
        self.db_factory = db_factory
        self.pipeline = pipeline
        self._task: asyncio.Task | None = None

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        while True:
            try:
                await self.tick()
            except Exception:
                logger.exception("Job runner tick failed")
            await asyncio.sleep(5)

    async def tick(self):
        db = self.db_factory()
        try:
            jobs = (
                db.query(SessionJob)
                .filter(SessionJob.status.notin_([JobStatus.COMPLETED, JobStatus.FAILED]))
                .order_by(SessionJob.deadline_at.asc())
                .all()
            )
            for job in jobs:
                if job.status == JobStatus.WAITING_GPU:
                    continue
                if job.status == JobStatus.AWAITING_REVIEW:
                    continue
                await self.pipeline.advance(db, job)
        finally:
            db.close()

    async def process_job(self, job_id: int):
        db = self.db_factory()
        try:
            job = db.query(SessionJob).filter(SessionJob.id == job_id).one()
            await self.pipeline.advance(db, job, force=True)
        finally:
            db.close()


class Pipeline:
    def __init__(self):
        from app.services.align import align_sources
        from app.services.audit import build_course_ir, persist_audit
        from app.services.extract import extract_all
        from app.services.git_sync import commit_session
        from app.services.latex import compile_session_documents
        from app.services.llm import generate_syllabus_content, generate_synthesis
        from app.services.publish import publish_to_drive
        from app.services.review import apply_auto_corrections, needs_review

        self.extract_all = extract_all
        self.align_sources = align_sources
        self.build_course_ir = build_course_ir
        self.persist_audit = persist_audit
        self.apply_auto_corrections = apply_auto_corrections
        self.needs_review = needs_review
        self.generate_syllabus_content = generate_syllabus_content
        self.generate_synthesis = generate_synthesis
        self.compile_session_documents = compile_session_documents
        self.commit_session = commit_session
        self.publish_to_drive = publish_to_drive

    async def advance(self, db: Session, job: SessionJob, force: bool = False):
        step = job.current_step or JobStep.INGEST
        work = Path(job.work_path)

        if step == JobStep.INGEST:
            if has_audio(job) and not has_transcription(job):
                update_job_status(db, job, JobStatus.WAITING_GPU, JobStep.TRANSCRIBE)
                return
            job.current_step = JobStep.EXTRACT
            db.commit()
            step = JobStep.EXTRACT

        if step == JobStep.EXTRACT:
            update_job_status(db, job, JobStatus.PROCESSING, JobStep.EXTRACT)
            await asyncio.to_thread(self.extract_all, job, work)
            job.current_step = JobStep.ALIGN
            db.commit()
            step = JobStep.ALIGN

        if step == JobStep.ALIGN:
            update_job_status(db, job, JobStatus.PROCESSING, JobStep.ALIGN)
            await asyncio.to_thread(self.align_sources, job, work)
            job.current_step = JobStep.AUDIT
            db.commit()
            step = JobStep.AUDIT

        if step == JobStep.AUDIT:
            update_job_status(db, job, JobStatus.PROCESSING, JobStep.AUDIT)
            course_ir = await asyncio.to_thread(self.build_course_ir, db, job, work)
            await asyncio.to_thread(self.persist_audit, job, work, course_ir)
            await asyncio.to_thread(self.apply_auto_corrections, db, job, course_ir)
            if self.needs_review(db, job):
                update_job_status(db, job, JobStatus.AWAITING_REVIEW, JobStep.REVIEW)
                return
            job.current_step = JobStep.GENERATE
            db.commit()
            step = JobStep.GENERATE

        if step == JobStep.REVIEW and force:
            job.current_step = JobStep.GENERATE
            db.commit()
            step = JobStep.GENERATE

        if step == JobStep.GENERATE:
            update_job_status(db, job, JobStatus.RENDERING, JobStep.GENERATE)
            await self.generate_syllabus_content(db, job, work)
            job.current_step = JobStep.SYNTHESIS
            db.commit()
            step = JobStep.SYNTHESIS

        if step == JobStep.SYNTHESIS:
            await self.generate_synthesis(db, job, work)
            job.current_step = JobStep.LATEX
            db.commit()
            step = JobStep.LATEX

        if step == JobStep.LATEX:
            await asyncio.to_thread(self.compile_session_documents, job, work)
            job.current_step = JobStep.GIT
            db.commit()
            step = JobStep.GIT

        if step == JobStep.GIT:
            await asyncio.to_thread(self.commit_session, job, work)
            job.current_step = JobStep.PUBLISH
            db.commit()
            step = JobStep.PUBLISH

        if step == JobStep.PUBLISH:
            await self.publish_to_drive(job, work)
            update_job_status(db, job, JobStatus.COMPLETED, JobStep.PUBLISH)


def claim_gpu_job(db: Session, worker_id: str, task_type: str = "transcribe") -> tuple[SessionJob, int] | None:
    settings = get_settings()
    job = (
        db.query(SessionJob)
        .filter(SessionJob.status == JobStatus.WAITING_GPU)
        .order_by(SessionJob.deadline_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if not job:
        return None
    token = 1
    existing = db.query(GpuLease).filter(GpuLease.job_id == job.id, GpuLease.task_type == task_type).first()
    if existing:
        token = existing.fencing_token + 1
        existing.worker_id = worker_id
        existing.fencing_token = token
        existing.lease_expires_at = datetime.utcnow() + timedelta(minutes=settings.ects_lease_minutes)
    else:
        db.add(
            GpuLease(
                job_id=job.id,
                worker_id=worker_id,
                fencing_token=token,
                lease_expires_at=datetime.utcnow() + timedelta(minutes=settings.ects_lease_minutes),
                task_type=task_type,
            )
        )
    job.status = JobStatus.PROCESSING
    job.current_step = JobStep.TRANSCRIBE
    db.commit()
    return job, token


def complete_gpu_transcription(db: Session, job_id: int, worker_id: str, fencing_token: int, text: str, work_path: Path):
    lease = db.query(GpuLease).filter(GpuLease.job_id == job_id, GpuLease.task_type == "transcribe").first()
    if not lease or lease.worker_id != worker_id or lease.fencing_token != fencing_token:
        raise PermissionError("Stale worker or invalid fencing token")
    out = work_path / "input" / "transcription_whisper.txt"
    out.write_text(text, encoding="utf-8")
    job = db.query(SessionJob).filter(SessionJob.id == job_id).one()
    job.current_step = JobStep.EXTRACT
    job.status = JobStatus.PENDING
    db.commit()
