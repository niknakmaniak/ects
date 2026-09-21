"""Tests ECTS."""

import pytest

from app.services.audit import build_course_ir, persist_audit
from app.services.extract import extract_all
from app.services.align import align_sources
from app.services.jobs import create_job, parse_session_folder
from app.services.subject_profile import load_profile, should_train_lora, update_profile_from_session
from app.services.pipeline import claim_gpu_job, complete_gpu_transcription
from app.db.models import JobStatus


def test_parse_session_folder():
    assert parse_session_folder("Psychologie__2026-09-15") == ("Psychologie", "2026-09-15")
    assert parse_session_folder("invalid") is None


def test_golden_psychologie_pipeline(db, tmp_path):
    fixture = tmp_path / "Psychologie__2026-09-15"
    src = __import__("pathlib").Path(__file__).parent / "fixtures" / "psychologie_2026-09-15"
    import shutil

    shutil.copytree(src, fixture)
    session = db
    job = create_job(session, fixture, "Psychologie__2026-09-15", "Psychologie", "2026-09-15")
    work = __import__("pathlib").Path(job.work_path)

    extract_all(job, work)
    align_sources(job, work)
    course_ir = build_course_ir(session, job, work)
    audit_path = persist_audit(job, work, course_ir)

    assert audit_path.exists()
    categories = {s.category.value for s in course_ir.audit_sections}
    assert "certain_error" in categories
    assert any("khun" in c.original.lower() for c in job.corrections)
    assert course_ir.subject == "Psychologie"


def test_gpu_claim_and_complete(db, tmp_path):
    session = db
    fixture = tmp_path / "Psychologie__2026-09-16"
    fixture.mkdir()
    (fixture / "READY.txt").write_text("x")
    (fixture / "audio.m4a").write_bytes(b"\x00")
    job = create_job(session, fixture, "Psychologie__2026-09-16", "Psychologie", "2026-09-16")
    job.status = JobStatus.WAITING_GPU
    session.commit()

    claimed = claim_gpu_job(session, "worker-a")
    assert claimed is not None
    j, token = claimed
    assert j.id == job.id

    work = __import__("pathlib").Path(j.work_path)
    complete_gpu_transcription(session, j.id, "worker-a", token, "Texte transcrit", work)
    assert (work / "input" / "transcription_whisper.txt").exists()


def test_gpu_stale_fencing_rejected(db, tmp_path):
    session = db
    fixture = tmp_path / "Psychologie__2026-09-17"
    fixture.mkdir()
    (fixture / "READY.txt").write_text("x")
    job = create_job(session, fixture, "Psychologie__2026-09-17", "Psychologie", "2026-09-17")
    job.status = JobStatus.WAITING_GPU
    session.commit()

    claim_gpu_job(session, "worker-a")
    with pytest.raises(PermissionError):
        complete_gpu_transcription(session, job.id, "worker-a", 999, "x", __import__("pathlib").Path(job.work_path))


def test_subject_profile_learning():
    profile = load_profile("Psychologie")
    assert profile["language"] == "fr"
    update_profile_from_session("Psychologie", {"sections": [{"heading": "Behaviorisme"}]})
    updated = load_profile("Psychologie")
    assert updated.get("session_count", 0) >= 1


def test_lora_threshold():
    from app.config import get_settings

    get_settings.cache_clear()
    profile = {"session_count": 3}
    from app.services import subject_profile as sp

    sp.save_profile("Test", profile)
    assert should_train_lora("Test") is True
