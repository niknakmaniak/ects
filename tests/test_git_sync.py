"""Tests Git commit/push."""

from pathlib import Path

from app.services.git_sync import commit_session


def test_git_commit_session(db, app_env, git_repo):
    subject_dir = app_env.sessions_dir / "psychologie" / "sessions" / "2026-09-21"
    subject_dir.mkdir(parents=True)
    (subject_dir / "syllabus.tex").write_text("\\documentclass{article}", encoding="utf-8")
    (subject_dir / "audit.md").write_text("# audit", encoding="utf-8")

    class FakeJob:
        subject = "Psychologie"
        session_date = "2026-09-21"
        slug = "Psychologie__2026-09-21"

    app_env.git_auto_push = False
    sha = commit_session(FakeJob(), Path("."))
    assert sha is not None
    assert git_repo.active_branch.name == "psychologie"
    assert (subject_dir / "syllabus.tex").read_text(encoding="utf-8")
