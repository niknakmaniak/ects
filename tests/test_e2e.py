"""Tests end-to-end du pipeline ECTS (local, sans VPS reel)."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.db.models import JobStatus, JobStep, SessionJob
from app.services.align import align_sources
from app.services.audit import build_course_ir, persist_audit
from app.services.extract import extract_all
from app.services.jobs import create_job
from app.services.latex import compile_session_documents
from app.services.llm import generate_syllabus_content, generate_synthesis
from app.services.review import apply_auto_corrections, needs_review
from app.services.upload import save_uploaded_session


@pytest.mark.asyncio
async def test_e2e_upload_to_outputs(db, app_env, git_repo, logged_in_client):
    """Panel upload → extract → audit → LLM stub → LaTeX → Git commit."""
    files = [
        ("transcription.txt", b"Goffman hospitalise. Khun cite."),
        ("support_prof.txt", b"Kuhn Milgram support."),
        ("syllabus_annuel.txt", b"Khun notes syllabus."),
    ]
    job, work_parent = save_uploaded_session(db, "Psychologie", "2026-09-21", files)
    work = Path(job.work_path)

    extract_all(job, work)
    align_sources(job, work)
    course_ir = build_course_ir(db, job, work)
    persist_audit(job, work, course_ir)
    apply_auto_corrections(db, job, course_ir)

    with patch("app.services.llm._call_llm", new=AsyncMock(return_value='{"title":"Psy","sections":[{"heading":"Intro","body":"Test"}]}')):
        await generate_syllabus_content(db, job, work)
        await generate_synthesis(db, job, work)

    compile_session_documents(job, work)

    out = work / "output"
    assert (out / "course_ir.json").exists()
    assert (out / "audit.md").exists()
    assert (out / "syllabus.tex").exists()
    assert (out / "synthese.md").exists()

    session_dest = app_env.sessions_dir / "psychologie" / "sessions" / "2026-09-21"
    assert session_dest.exists()

    from app.services.git_sync import commit_session

    app_env.git_auto_push = False
    sha = commit_session(job, work)
    assert sha is not None

    repo = git_repo
    assert repo.active_branch.name == "psychologie"
    assert any("syllabus" in c.message for c in repo.iter_commits(max_count=3))


@pytest.mark.asyncio
async def test_e2e_panel_upload_via_http(logged_in_client, db):
    files = [
        ("files", ("audio.txt", b"contenu oral test", "text/plain")),
        ("files", ("support.txt", b"Kuhn support", "text/plain")),
    ]
    data = {"subject": "Droit", "session_date": "2026-09-22"}
    r = logged_in_client.post("/panel/upload", data=data, files=files, follow_redirects=False)
    assert r.status_code == 303

    job = db.query(SessionJob).filter(SessionJob.subject == "Droit").one()
    assert job.status == JobStatus.PENDING
    assert (Path(job.work_path) / "input" / "READY.txt").exists()


def test_e2e_gpu_download_and_complete(logged_in_client, db, app_env):
    from app.services.upload import save_uploaded_session

    job, _ = save_uploaded_session(
        db,
        "Psychologie",
        "2026-09-23",
        [("course.m4a", b"\x00\x01fake audio")],
    )
    job.status = JobStatus.WAITING_GPU
    db.commit()

    headers = {"Authorization": "Bearer test-gpu-token"}
    r = logged_in_client.post("/v1/gpu/claim", params={"worker_id": "e2e-worker"}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["job_id"] == job.id

    r2 = logged_in_client.get(
        f"/v1/gpu/{job.id}/audio/course.m4a",
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.content == b"\x00\x01fake audio"

    r3 = logged_in_client.post(
        f"/v1/gpu/{job.id}/complete",
        headers=headers,
        json={
            "worker_id": "e2e-worker",
            "fencing_token": data["fencing_token"],
            "transcription": "Texte transcrit e2e",
        },
    )
    assert r3.status_code == 200
    work = Path(job.work_path)
    assert (work / "input" / "transcription_whisper.txt").read_text(encoding="utf-8") == "Texte transcrit e2e"
