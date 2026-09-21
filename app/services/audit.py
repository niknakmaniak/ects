import json
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import CorrectionItem, CorrectionStatus
from app.models.course_ir import (
    AuditCategory,
    AuditSection,
    CourseIR,
    CourseItem,
    SourceRef,
    SourceType,
    TaughtStatus,
)


AUDIT_TITLES = {
    AuditCategory.RESOLVED: "1. Ce que l'audio a tranché",
    AuditCategory.CERTAIN_ERROR: "2. Erreurs certaines (à corriger)",
    AuditCategory.PROBABLE: "3. Probable",
    AuditCategory.LITERATURE_DEVIATION: "4. Le cours s'écarte de la littérature (garder la version du prof, avec une note)",
    AuditCategory.UNCERTAIN: "5. Toujours incertain",
    AuditCategory.OMISSION: "6. Omissions du syllabus (dit à l'oral, absent du texte)",
}


def _split_sections(text: str, max_items: int = 40) -> list[str]:
    chunks = [c.strip() for c in re.split(r"\n{2,}", text) if c.strip()]
    return chunks[:max_items]


def build_course_ir(db: Session, job, work: Path) -> CourseIR:
    aligned_path = work / "aligned" / "aligned.json"
    aligned = json.loads(aligned_path.read_text(encoding="utf-8"))
    items: list[CourseItem] = []
    sections: dict[AuditCategory, list[dict]] = {cat: [] for cat in AuditCategory}

    # Erreurs certaines — noms propres
    for fix in aligned.get("name_fixes_detected", []):
        item = CourseItem(
            id=f"fix-{fix['wrong']}",
            text=f"{fix['wrong']} → {fix['right']}",
            section="Orthographe / noms propres",
            taught_status=TaughtStatus.BOTH,
            audit_category=AuditCategory.CERTAIN_ERROR,
            sources=[SourceRef(type=SourceType.SUPPORT, ref="support", excerpt=fix["right"])],
            corrections=[
                {
                    "original": fix["wrong"],
                    "proposed": fix["right"],
                    "confidence": 0.95,
                    "evidence": "Support professeur / convention académique",
                    "status": "pending",
                    "verdict": "Correction orthographique certaine",
                }
            ],
        )
        items.append(item)
        sections[AuditCategory.CERTAIN_ERROR].append(
            {
                "location": "Syllabus / Support",
                "error": fix["wrong"],
                "correction": fix["right"],
                "verdict": "Correction certaine",
            }
        )
        db.add(
            CorrectionItem(
                job_id=job.id,
                audit_category=AuditCategory.CERTAIN_ERROR.value,
                location="Syllabus / Support",
                original=fix["wrong"],
                proposed=fix["right"],
                confidence=0.95,
                evidence="Support professeur",
                verdict="Correction certaine",
            )
        )

    # Conflits oral/support
    for conflict in aligned.get("conflicts", []):
        items.append(
            CourseItem(
                id=f"conflict-{conflict['topic']}",
                text=conflict["note"],
                section="Alignement sources",
                taught_status=TaughtStatus.UNCERTAIN,
                audit_category=AuditCategory.RESOLVED,
                sources=[
                    SourceRef(type=SourceType.AUDIO, ref="audio", excerpt="oral"),
                    SourceRef(type=SourceType.SUPPORT, ref="support", excerpt="support"),
                ],
            )
        )
        sections[AuditCategory.RESOLVED].append(
            {
                "point": conflict["topic"],
                "transcription": "Voir audio",
                "verdict": conflict["note"],
            }
        )

    # Omissions heuristiques — phrases oral absentes du syllabus
    audio_chunks = _split_sections(aligned.get("audio_excerpt", ""))
    syllabus_lower = aligned.get("syllabus_excerpt", "").lower()
    for i, chunk in enumerate(audio_chunks[:15]):
        key = chunk[:60].lower()
        if len(chunk) < 40:
            continue
        if key[:30] not in syllabus_lower and len(chunk.split()) > 8:
            priority = "fort" if any(w in chunk.lower() for w in ("freud", "waton", "important", "jamais")) else "moyen"
            items.append(
                CourseItem(
                    id=f"omission-{i}",
                    text=chunk[:500],
                    section="Oral",
                    taught_status=TaughtStatus.ORAL,
                    audit_category=AuditCategory.OMISSION,
                    priority=priority,
                    sources=[SourceRef(type=SourceType.AUDIO, ref="audio", excerpt=chunk[:200])],
                )
            )
            sections[AuditCategory.OMISSION].append(
                {
                    "section": "Oral",
                    "missing": chunk[:200],
                    "interest": priority,
                }
            )

    # Écarts littérature — patterns connus psy
    literature_patterns = [
        ("renforcement négatif", "Retirer le dessert — version du prof ; noter l'écart avec la littérature."),
        ("goffman", "Confusion probable avec Rosenhan (1973) — garder le récit du prof avec note."),
        ("watson", "Dates historiques erronées à l'oral — ne pas corriger silencieusement."),
    ]
    audio_lower = aligned.get("audio_excerpt", "").lower()
    for keyword, note in literature_patterns:
        if keyword in audio_lower:
            sections[AuditCategory.LITERATURE_DEVIATION].append(
                {"point": keyword, "course": "Version prof (oral)", "literature": note, "verdict": note}
            )
            items.append(
                CourseItem(
                    id=f"lit-{keyword[:8]}",
                    text=note,
                    section="Littérature",
                    taught_status=TaughtStatus.ORAL,
                    audit_category=AuditCategory.LITERATURE_DEVIATION,
                    sources=[SourceRef(type=SourceType.AUDIO, ref="audio", excerpt=keyword)],
                )
            )

    audit_sections = [
        AuditSection(title=AUDIT_TITLES[cat], category=cat, rows=sections[cat]) for cat in AuditCategory if sections[cat]
    ]

    course_ir = CourseIR(
        subject=job.subject,
        session_date=job.session_date,
        items=items,
        audit_sections=audit_sections,
        metadata={"slug": job.slug},
    )
    db.commit()
    return course_ir


def persist_audit(job, work: Path, course_ir: CourseIR) -> Path:
    out_dir = work / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    ir_path = out_dir / "course_ir.json"
    ir_path.write_text(course_ir.model_dump_json(indent=2), encoding="utf-8")

    md_lines = [
        f"# {course_ir.subject} — Analyse du syllabus",
        f"Séance du {course_ir.session_date}",
        "",
        "Abréviations : « Syll. » = syllabus annuel · « Sup. » = support du professeur.",
        "",
    ]
    for section in course_ir.audit_sections:
        md_lines.append(f"## {section.title}")
        md_lines.append("")
        if not section.rows:
            md_lines.append("_Aucun élément._")
        for row in section.rows:
            md_lines.append("| " + " | ".join(str(v) for v in row.values()) + " |")
        md_lines.append("")

    audit_md = out_dir / "audit.md"
    audit_md.write_text("\n".join(md_lines), encoding="utf-8")
    return audit_md
