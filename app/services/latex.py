import json
import logging
import shutil
import subprocess
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


def _escape_latex(text: str) -> str:
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for k, v in repl.items():
        text = text.replace(k, v)
    return text


def render_syllabus_tex(job, work: Path, content: dict) -> Path:
    settings = get_settings()
    sections_tex = []
    for sec in content.get("sections", []):
        heading = _escape_latex(sec.get("heading", "Section"))
        body = _escape_latex(sec.get("body", ""))
        sections_tex.append(f"\\section{{{heading}}}\n{body}\n")

    template = (settings.latex_templates_dir / "syllabus.tex").read_text(encoding="utf-8")
    tex = (
        template.replace("{{SUBJECT}}", _escape_latex(job.subject))
        .replace("{{SESSION_DATE}}", _escape_latex(job.session_date))
        .replace("{{TITLE}}", _escape_latex(content.get("title", job.subject)))
        .replace("{{CONTENT}}", "\n".join(sections_tex))
    )
    out = work / "output" / "syllabus.tex"
    out.write_text(tex, encoding="utf-8")
    return out


def render_audit_tex(job, work: Path) -> Path:
    settings = get_settings()
    audit_md = (work / "output" / "audit.md").read_text(encoding="utf-8")
    body = _escape_latex(audit_md)
    template = (settings.latex_templates_dir / "audit.tex").read_text(encoding="utf-8")
    tex = (
        template.replace("{{SUBJECT}}", _escape_latex(job.subject))
        .replace("{{SESSION_DATE}}", _escape_latex(job.session_date))
        .replace("{{CONTENT}}", f"\\begin{{verbatim}}\n{audit_md}\n\\end{{verbatim}}")
    )
    out = work / "output" / "audit.tex"
    out.write_text(tex, encoding="utf-8")
    return out


def render_synthese_tex(job, work: Path) -> Path:
    settings = get_settings()
    md = (work / "output" / "synthese.md").read_text(encoding="utf-8")
    template = (settings.latex_templates_dir / "synthese.tex").read_text(encoding="utf-8")
    tex = (
        template.replace("{{SUBJECT}}", _escape_latex(job.subject))
        .replace("{{SESSION_DATE}}", _escape_latex(job.session_date))
        .replace("{{CONTENT}}", f"\\begin{{verbatim}}\n{md}\n\\end{{verbatim}}")
    )
    out = work / "output" / "synthese.tex"
    out.write_text(tex, encoding="utf-8")
    return out


def _compile_tex(tex_path: Path) -> Path:
    settings = get_settings()
    out_dir = tex_path.parent
    tectonic = shutil.which("tectonic")
    if tectonic:
        subprocess.run([tectonic, "-X", "compile", str(tex_path), "--outdir", str(out_dir)], check=False, capture_output=True)
    else:
        pdflatex = shutil.which("pdflatex")
        if pdflatex:
            subprocess.run([pdflatex, "-interaction=nonstopmode", "-output-directory", str(out_dir), str(tex_path)], check=False)
        else:
            logger.warning("Ni tectonic ni pdflatex trouvé — PDF non généré")
            return tex_path.with_suffix(".pdf")
    return tex_path.with_suffix(".pdf")


def compile_session_documents(job, work: Path):
    settings = get_settings()
    cls_src = settings.latex_templates_dir / "ects.cls"
    if cls_src.exists():
        shutil.copy2(cls_src, work / "output" / "ects.cls")

    content_path = work / "output" / "syllabus_content.json"
    content = json.loads(content_path.read_text(encoding="utf-8")) if content_path.exists() else {"title": job.subject, "sections": []}
    render_syllabus_tex(job, work, content)
    render_audit_tex(job, work)
    render_synthese_tex(job, work)
    for name in ("syllabus", "audit", "synthese"):
        _compile_tex(work / "output" / f"{name}.tex")

    settings = get_settings()
    dest = settings.sessions_dir / job.subject.lower().replace(" ", "_") / "sessions" / job.session_date
    dest.mkdir(parents=True, exist_ok=True)
    for fname in ("course_ir.json", "audit.md", "audit.tex", "syllabus.tex", "synthese.md", "syllabus_content.json"):
        src = work / "output" / fname
        if src.exists():
            shutil.copy2(src, dest / fname)
    for pdf in (work / "output").glob("*.pdf"):
        shutil.copy2(pdf, dest / pdf.name)
