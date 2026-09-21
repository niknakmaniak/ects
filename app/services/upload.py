import re
import shutil
from datetime import date
from pathlib import Path

from app.config import get_settings
from app.services.jobs import create_job, parse_session_folder

ALLOWED_EXTENSIONS = {
    ".m4a", ".mp3", ".wav", ".aac",
    ".pdf", ".ppt", ".pptx", ".doc", ".docx",
    ".txt", ".md", ".vtt", ".srt",
}

SUBJECT_PATTERN = re.compile(r"^[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9 _-]{1,60}$")


def slugify_subject(subject: str) -> str:
    cleaned = subject.strip().replace(" ", "_")
    cleaned = re.sub(r"[^A-Za-zÀ-ÿ0-9_-]", "", cleaned)
    return cleaned


def build_session_slug(subject: str, session_date: str) -> str:
    return f"{slugify_subject(subject)}__{session_date}"


def validate_subject(subject: str) -> str:
    subject = subject.strip()
    if not SUBJECT_PATTERN.match(subject):
        raise ValueError("Nom de matière invalide")
    return subject


def validate_session_date(session_date: str) -> str:
    try:
        date.fromisoformat(session_date)
    except ValueError as exc:
        raise ValueError("Date invalide (YYYY-MM-DD)") from exc
    return session_date


def list_known_subjects() -> list[str]:
    settings = get_settings()
    subjects = set()
    if settings.profiles_dir.exists():
        for p in settings.profiles_dir.glob("*.json"):
            subjects.add(p.stem.replace("_", " ").title())
    return sorted(subjects)


def save_uploaded_session(db, subject: str, session_date: str, files: list[tuple[str, bytes]]) -> tuple[object, Path]:
    subject = validate_subject(subject)
    session_date = validate_session_date(session_date)
    slug = build_session_slug(subject, session_date)

    settings = get_settings()
    inbox_dir = settings.ects_data_dir / "inbox" / slug
    if inbox_dir.exists():
        shutil.rmtree(inbox_dir)
    input_dir = inbox_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for name, data in files:
        safe_name = Path(name).name
        if not safe_name or safe_name in {".", ".."}:
            continue
        ext = Path(safe_name).suffix.lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            continue
        (input_dir / safe_name).write_bytes(data)
        saved += 1

    if saved == 0:
        shutil.rmtree(inbox_dir, ignore_errors=True)
        raise ValueError("Aucun fichier accepté")

    (inbox_dir / "READY.txt").write_text("ready\n", encoding="utf-8")
    parsed = parse_session_folder(slug)
    if not parsed:
        parsed_subject, parsed_date = subject, session_date
    else:
        parsed_subject, parsed_date = parsed

    job = create_job(db, inbox_dir, slug, parsed_subject, parsed_date)
    return job, inbox_dir
