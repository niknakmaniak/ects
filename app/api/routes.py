from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from app.db.models import JobStatus, SessionJob, get_session_factory
from app.services.pipeline import claim_gpu_job, complete_gpu_transcription

router = APIRouter()


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


@router.get("/")
def root_redirect():
    from fastapi.responses import RedirectResponse

    return RedirectResponse("/panel", status_code=303)


@router.get("/health")
def health():
    return {"status": "ok", "service": "ects"}


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


@router.get("/v1/gpu/{job_id}/audio/{filename}")
def gpu_download_audio(job_id: int, filename: str, db=Depends(get_db), role=Depends(verify_token)):
    if role != "gpu":
        raise HTTPException(403, "GPU token required")
    job = db.query(SessionJob).filter(SessionJob.id == job_id).first()
    if not job:
        raise HTTPException(404)
    if job.status not in (JobStatus.WAITING_GPU, JobStatus.PROCESSING):
        raise HTTPException(409, "Job not available for GPU download")
    from app.services.jobs import list_input_files

    allowed = {p.name for p in list_input_files(job) if p.suffix.lower() in {".m4a", ".mp3", ".wav", ".aac"}}
    if filename not in allowed:
        raise HTTPException(404, "Audio file not found")
    path = Path(job.work_path) / "input" / filename
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, filename=filename)


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
