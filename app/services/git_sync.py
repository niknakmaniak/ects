import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from git import Repo

from app.config import get_settings

logger = logging.getLogger(__name__)


def commit_session(job, work: Path):
    settings = get_settings()
    repo_path = settings.ects_repo_root
    subject_slug = job.subject.lower().replace(" ", "_")
    session_dest = settings.sessions_dir / subject_slug / "sessions" / job.session_date

    if not session_dest.exists():
        logger.warning("Session dest missing: %s", session_dest)
        return

    try:
        repo = Repo(repo_path)
    except Exception:
        logger.warning("Pas un repo Git — skip commit")
        return

    branch = subject_slug
    if branch in repo.heads:
        repo.heads[branch].checkout()
    else:
        repo.create_head(branch).checkout()

    repo.index.add([str(session_dest.relative_to(repo_path))])
    msg = f"{subject_slug}: syllabus {job.session_date} + audit + synthese"
    if not repo.is_dirty(untracked_files=False):
        logger.info("Rien à committer")
        return
    repo.index.commit(msg, author=__import__("git").Actor(settings.git_user_name, settings.git_user_email))

    if settings.git_auto_push and settings.git_remote_url:
        try:
            repo.remote("origin").push(branch)
        except Exception as e:
            logger.warning("Push failed: %s", e)
