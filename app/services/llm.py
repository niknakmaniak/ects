import json
import logging
from pathlib import Path

from app.config import get_settings
from app.services.subject_profile import load_profile, update_profile_from_session

logger = logging.getLogger(__name__)


async def _call_llm(system: str, user: str) -> str:
    settings = get_settings()
    if not settings.llm_api_key:
        logger.warning("LLM_API_KEY absent — mode stub")
        return _stub_response(user)

    if settings.llm_provider in ("openai", "moonshot"):
        from openai import OpenAI

        kwargs = {"api_key": settings.llm_api_key}
        if settings.llm_provider == "moonshot" or settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url or "https://api.moonshot.cn/v1"
        client = OpenAI(**kwargs)
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""

    raise ValueError(f"Provider inconnu: {settings.llm_provider}")


def _stub_response(user: str) -> str:
    return json.dumps(
        {
            "title": "Syllabus de séance",
            "sections": [
                {"heading": "Introduction", "body": "Contenu généré en mode stub (configurer LLM_API_KEY)."},
                {"heading": "Points clés", "body": user[:500]},
            ],
        },
        ensure_ascii=False,
    )


async def generate_syllabus_content(db, job, work: Path):
    settings = get_settings()
    ir_path = work / "output" / "course_ir.json"
    course_ir = json.loads(ir_path.read_text(encoding="utf-8"))
    profile = load_profile(job.subject)
    lora_hint = ""
    if profile.get("lora_adapter_path"):
        lora_hint = f" Adapter LoRA : {profile['lora_adapter_path']}."
    system = (
        "Tu rédiges un syllabus universitaire en français à partir d'un CourseIR JSON strict. "
        "N'invente aucun fait. Utilise uniquement les items du JSON. "
        "Style : notes d'étudiant très bien mises au propre, pas encyclopédique. "
        f"Profil matière : {json.dumps(profile, ensure_ascii=False)}.{lora_hint}"
    )
    user = json.dumps(course_ir, ensure_ascii=False)
    raw = await _call_llm(system, user)
    try:
        content = json.loads(raw)
    except json.JSONDecodeError:
        content = {"title": f"{job.subject} — {job.session_date}", "sections": [{"heading": "Contenu", "body": raw}]}

    (work / "output" / "syllabus_content.json").write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    update_profile_from_session(job.subject, content)
    job.llm_cost_eur += 0.01
    db.commit()


async def generate_synthesis(db, job, work: Path):
    ir_path = work / "output" / "course_ir.json"
    course_ir = json.loads(ir_path.read_text(encoding="utf-8"))

    system = (
        "Tu produis une mini-synthèse pour préparer le prochain cours. "
        "Format markdown court : ce que le prof a dit, points à retenir, questions ouvertes. "
        "Uniquement à partir du CourseIR fourni."
    )
    raw = await _call_llm(system, json.dumps(course_ir, ensure_ascii=False))
    (work / "output" / "synthese.md").write_text(raw, encoding="utf-8")
    job.llm_cost_eur += 0.005
    db.commit()
