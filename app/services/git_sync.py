import logging
from pathlib import Path

from git import Actor, Repo

from app.config import get_settings

logger = logging.getLogger(__name__)


def _subject_slug(subject: str) -> str:
    return subject.lower().replace(" ", "_")


def _ensure_origin(repo: Repo):
    settings = get_settings()
    url = settings.git_remote_url
    if settings.git_github_token and url.startswith("https://"):
        url = url.replace("https://", f"https://{settings.git_github_token}@")
    if "origin" in [r.name for r in repo.remotes]:
        repo.remotes.origin.set_url(url)
    else:
        repo.create_remote("origin", url)


def commit_session(job, work: Path) -> str | None:
    """Commit les artefacts de session sur la branche matiere ; push si GIT_AUTO_PUSH."""
    settings = get_settings()
    repo_path = settings.ects_repo_root.resolve()
    subject_slug = _subject_slug(job.subject)
    session_dest = settings.sessions_dir / subject_slug / "sessions" / job.session_date

    if not session_dest.exists():
        logger.warning("Session dest missing: %s", session_dest)
        return None

    if not (repo_path / ".git").exists():
        logger.warning("Pas de repo Git dans %s — skip commit", repo_path)
        return None

    repo = Repo(repo_path)
    _ensure_origin(repo)

    with repo.config_writer() as cw:
        cw.set_value("user", "name", settings.git_user_name)
        cw.set_value("user", "email", settings.git_user_email)

    branch = subject_slug
    if branch in repo.heads:
        repo.heads[branch].checkout()
    else:
        repo.create_head(branch).checkout()

    rel = session_dest.relative_to(repo_path)
    files = [str(p.relative_to(repo_path)) for p in session_dest.rglob("*") if p.is_file()]
    if not files:
        return None
    repo.index.add(files)

    if not repo.is_dirty(untracked_files=True):
        logger.info("Rien a committer pour %s", job.slug)
        return None

    msg = f"{subject_slug}: syllabus {job.session_date} + audit + synthese"
    commit = repo.index.commit(msg, author=Actor(settings.git_user_name, settings.git_user_email))
    logger.info("Git commit %s on %s", commit.hexsha[:8], branch)

    if settings.git_auto_push:
        push_branch(repo, branch)

    return commit.hexsha


def push_branch(repo: Repo, branch: str):
    settings = get_settings()
    _ensure_origin(repo)
    try:
        repo.remotes.origin.push(refspec=f"{branch}:{branch}")
        logger.info("Git push OK: %s", branch)
    except Exception as e:
        logger.error("Git push failed (%s): %s", branch, e)
        raise


def _collect_files(folder: Path) -> list[str]:
    return [str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file()]