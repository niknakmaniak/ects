"""Tests upload et validation."""

import pytest

from app.services.upload import (
    build_session_slug,
    save_uploaded_session,
    validate_session_date,
    validate_subject,
)


def test_validate_subject():
    assert validate_subject("Psychologie") == "Psychologie"
    with pytest.raises(ValueError):
        validate_subject("")


def test_validate_date():
    assert validate_session_date("2026-09-21") == "2026-09-21"
    with pytest.raises(ValueError):
        validate_session_date("invalid")


def test_build_slug():
    assert build_session_slug("Psychologie", "2026-09-21") == "Psychologie__2026-09-21"


def test_save_upload_rejects_empty(db, app_env):
    with pytest.raises(ValueError, match="Aucun fichier"):
        save_uploaded_session(db, "Psychologie", "2026-09-21", [])


def test_save_upload_creates_job(db, app_env):
    job, folder = save_uploaded_session(
        db,
        "Psychologie",
        "2026-09-21",
        [("notes.txt", b"hello")],
    )
    assert job.slug == "Psychologie__2026-09-21"
    assert (folder / "READY.txt").exists()
