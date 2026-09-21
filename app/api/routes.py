from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.db.models import CorrectionStatus, JobStatus, SessionJob, get_session_factory
from app.services.pipeline import claim_gpu_job, complete_gpu_transcription
from app.services.review import approve_correction

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def get_db():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def verify_token(request: Request):
    from app.config import get_settings

    settings = get_settings()
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {settings.ects_api_token}":
        return "api"
    if auth == f"Bearer {settings.ects_gpu_worker_token}":
        return "gpu"
    raise HTTPException(401, "Unauthorized")


class GpuClaimResponse(BaseModel):
    job_id: int
    slug: str
    work_path: str
    audio_files: list[str]
    fencing_token: int


class GpuCompleteRequest(BaseModel):
    worker_id: str
    fencing_token: int
    transcription: str


@router.get("/health")
def health():
    return {"status": "ok", "service": "ects"}


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db=Depends(get_db)):
    jobs = db.query(SessionJob).order_by(SessionJob.created_at.desc()).limit(50).all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "jobs": jobs, "JobStatus": JobStatus})


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int, db=Depends(get_db)):
    job = db.query(SessionJob).filter(SessionJob.id == job_id).first()
    if not job:
        raise HTTPException(404)
    corrections = [c for c in job.corrections if c.status == CorrectionStatus.PENDING]
    return templates.TemplateResponse(
        "job_detail.html", {"request": request, "job": job, "corrections": corrections, "JobStatus": JobStatus}
    )


@router.post("/jobs/{job_id}/approve-review")
def approve_review(job_id: int, db=Depends(get_db), _=Depends(verify_token)):
    job = db.query(SessionJob).filter(SessionJob.id == job_id).first()
    if not job or job.status != JobStatus.AWAITING_REVIEW:
        raise HTTPException(400, "Job not awaiting review")
    job.status = JobStatus.PENDING
    job.current_step = __import__("app.db.models", fromlist=["JobStep"]).JobStep.GENERATE
    db.commit()
    return {"ok": True}


@router.post("/corrections/{correction_id}/decide")
def decide_correction(correction_id: int, approved: bool, db=Depends(get_db), _=Depends(verify_token)):
    item = approve_correction(db, correction_id, approved)
    return {"id": item.id, "status": item.status.value}


@router.post("/v1/gpu/claim", response_model=GpuClaimResponse | None)
def gpu_claim(worker_id: str = "gpu-1", db=Depends(get_db), role=Depends(verify_token)):
    if role != "gpu":
        raise HTTPException(403, "GPU token required")
    result = claim_gpu_job(db, worker_id)
    if not result:
        return None
    job, token = result
    from app.services.jobs import list_input_files

    audio_files = [str(p.name) for p in list_input_files(job) if p.suffix.lower() in {".m4a", ".mp3", ".wav"}]
    return GpuClaimResponse(
        job_id=job.id, slug=job.slug, work_path=job.work_path, audio_files=audio_files, fencing_token=token
    )


@router.post("/v1/gpu/{job_id}/complete")
def gpu_complete(job_id: int, body: GpuCompleteRequest, db=Depends(get_db), role=Depends(verify_token)):
    if role != "gpu":
        raise HTTPException(403, "GPU token required")
    job = db.query(SessionJob).filter(SessionJob.id == job_id).first()
    if not job:
        raise HTTPException(404)
    try:
        complete_gpu_transcription(db, job_id, body.worker_id, body.fencing_token, body.transcription, Path(job.work_path))
    except PermissionError:
        raise HTTPException(409, "Stale worker or invalid fencing token")
    return {"ok": True}


@router.post("/v1/intake/scan")
def intake_scan(db=Depends(get_db), _=Depends(verify_token)):
    from app.services.drive import IntakeService

    intake = IntakeService(get_session_factory)
    jobs = intake.scan_all()
    return {"ingested": [j.slug for j in jobs]}


@router.post("/v1/lora/train")
def trigger_lora(subject: str, _=Depends(verify_token)):
    import subprocess
    import sys

    from app.config import get_settings
    from app.services.subject_profile import load_profile, save_profile, should_train_lora

    settings = get_settings()
    if not should_train_lora(subject):
        raise HTTPException(400, f"Minimum {settings.lora_min_sessions} sessions requises")
    result = subprocess.run(
        [sys.executable, "worker-gpu/worker.py", "--mode", "lora", "--subject", subject],
        cwd=str(settings.ects_repo_root),
        capture_output=True,
        text=True,
    )
    profile = load_profile(subject)
    adapter_path = str(settings.lora_output_dir / f"{subject.lower().replace(' ', '_')}_lora")
    profile["lora_adapter_path"] = adapter_path
    save_profile(subject, profile)
    return {"adapter_path": adapter_path, "returncode": result.returncode}
