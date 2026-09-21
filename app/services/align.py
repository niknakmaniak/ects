import json
import re
from pathlib import Path

NAME_FIXES = {
    "khun": "Kuhn",
    "millgram": "Milgram",
    "selligman": "Seligman",
    "ash": "Asch",
    "vigotsky": "Vygotski",
    "lipovestky": "Lipovetsky",
    "laplache": "Laplanche",
    "van dreybroek": "Van Reybrouck",
    "maslach [?]": "Christina Maslach",
    "facuté": "FACULTÉ",
    "mannette": "manette",
    "courrant": "courant",
    "stimulis": "stimuli",
}


def align_sources(job, work: Path) -> dict:
    bundle_path = work / "extracted" / "bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    aligned = {
        "subject": job.subject,
        "session_date": job.session_date,
        "syllabus_excerpt": bundle.get("syllabus", "")[:8000],
        "support_excerpt": bundle.get("support", "")[:8000],
        "audio_excerpt": bundle.get("audio", "")[:12000],
        "name_fixes_detected": [],
    }

    combined = (bundle.get("syllabus", "") + bundle.get("support", "")).lower()
    for wrong, right in NAME_FIXES.items():
        if wrong in combined:
            aligned["name_fixes_detected"].append({"wrong": wrong, "right": right})

    # Détection simple oral vs support (inversions, contradictions)
    aligned["conflicts"] = []
    audio = bundle.get("audio", "").lower()
    support = bundle.get("support", "").lower()
    if "groupe 1" in audio and "groupe 2" in audio and "cage" in support:
        aligned["conflicts"].append(
            {
                "topic": "groupes_inverses",
                "rule": "support_wins",
                "note": "Documenter l'écart oral/support ; le support l'emporte pour les faits.",
            }
        )

    (work / "aligned" / "aligned.json").parent.mkdir(parents=True, exist_ok=True)
    (work / "aligned" / "aligned.json").write_text(json.dumps(aligned, indent=2, ensure_ascii=False), encoding="utf-8")
    return aligned
