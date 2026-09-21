from datetime import datetime, timedelta
import hashlib
import json
import re
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Artifact, JobStatus, JobStep, SessionJob


SESSION_DIR_PATTERN = re.compile(r"^(.+)__(\d{4}-\d{2}-\d{2})$")


def parse_session_folder(name: str) -> tuple[str, str] | None:
    match = SESSION_DIR_PATTERN.match(name.strip())
    if not match:
        return None
    subject = match.group(1).replace("_", " ").strip()
    return subject, match.group(2)


def compute_deadline(from_dt: datetime | None = None) -> datetime:
    settings = get_settings()
    base = from_dt or datetime.now()
    target = base.replace(hour=settings.ects_default_deadline_hour, minute=0, second=0, microsecond=0)
    if target <= base:
        target += timedelta(days=1)
    return target


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_session(source_dir: Path, slug: str) -> Path:
    settings = get_settings()
    dest = settings.work_dir / slug / "input"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source_dir, dest)
    manifest = {
        "slug": slug,
        "files": [
            {"name": p.name, "sha256": sha256_file(p), "size": p.stat().st_size}
            for p in sorted(dest.rglob("*"))
            if p.is_file()
        ],
    }
    manifest_path = settings.work_dir / slug / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return dest


def create_job(db: Session, source_dir: Path, slug: str, subject: str, session_date: str) -> SessionJob:
    settings = get_settings()
    work_path = snapshot_session(source_dir, slug)
    commit_hash = hashlib.sha256(work_path.as_posix().encode()).hexdigest()[:16]
    job = SessionJob(
        slug=slug,
        subject=subject,
        session_date=session_date,
        status=JobStatus.PENDING,
        current_step=JobStep.INGEST,
        deadline_at=compute_deadline(),
        work_path=str(work_path.parent),
        source_commit_hash=commit_hash,
    )
    db.add(job)
    db.flush()
    for p in work_path.rglob("*"):
        if p.is_file():
            db.add(
                Artifact(
                    job_id=job.id,
                    kind=p.suffix.lstrip(".").lower() or "file",
                    path=str(p.relative_to(work_path.parent)),
                    sha256=sha256_file(p),
                )
            )
    db.commit()
    db.refresh(job)
    return job


def list_input_files(job: SessionJob) -> list[Path]:
    input_dir = Path(job.work_path) / "input"
    return [p for p in sorted(input_dir.rglob("*")) if p.is_file()]


def has_audio(job: SessionJob) -> bool:
    return any(p.suffix.lower() in {".m4a", ".mp3", ".wav", ".aac"} for p in list_input_files(job))


def has_transcription(job: SessionJob) -> bool:
    ignore = {"ready.txt"}
    for p in list_input_files(job):
        name = p.name.lower()
        if name in ignore:
            continue
        if name == "transcription_whisper.txt":
            return True
        if "transcript" in name:
            return True
        if name.endswith((".vtt", ".srt")):
            return True
    return False


def update_job_status(db: Session, job: SessionJob, status: JobStatus, step: JobStep | None = None, error: str | None = None):
    job.status = status
    if step:
        job.current_step = step
    if error:
        job.error_message = error
    job.updated_at = datetime.utcnow()
    db.commit()
