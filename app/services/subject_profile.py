import json
from pathlib import Path

from app.config import get_settings
from app.db.models import SubjectProfile, get_session_factory


DEFAULT_PROFILE = {
    "heading_depth": 3,
    "section_order": ["Introduction", "Concepts clés", "Applications", "À retenir"],
    "tone": "notes_etudiant",
    "language": "fr",
}


def load_profile(subject: str) -> dict:
    settings = get_settings()
    path = settings.profiles_dir / f"{subject.lower().replace(' ', '_')}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {**DEFAULT_PROFILE, "subject": subject}


def save_profile(subject: str, profile: dict):
    settings = get_settings()
    settings.profiles_dir.mkdir(parents=True, exist_ok=True)
    path = settings.profiles_dir / f"{subject.lower().replace(' ', '_')}.json"
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def update_profile_from_session(subject: str, syllabus_content: dict):
    profile = load_profile(subject)
    headings = [s.get("heading", "") for s in syllabus_content.get("sections", []) if s.get("heading")]
    if headings:
        profile["learned_headings"] = headings[-20:]
    profile["session_count"] = profile.get("session_count", 0) + 1
    save_profile(subject, profile)

    db = get_session_factory()()
    try:
        row = db.query(SubjectProfile).filter(SubjectProfile.subject == subject).first()
        if row:
            row.session_count = profile["session_count"]
            row.profile_json = profile
        else:
            db.add(SubjectProfile(subject=subject, session_count=1, profile_json=profile))
        db.commit()
    finally:
        db.close()


def should_train_lora(subject: str) -> bool:
    settings = get_settings()
    profile = load_profile(subject)
    return profile.get("session_count", 0) >= settings.lora_min_sessions


def get_lora_adapter(subject: str) -> str | None:
    profile = load_profile(subject)
    return profile.get("lora_adapter_path")
