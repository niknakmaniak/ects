from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.panel_auth import is_authenticated, login_user, logout_user, redirect_if_not_auth
from app.db.models import CorrectionStatus, JobStatus, SessionJob, get_session_factory
from app.services.upload import list_known_subjects, save_uploaded_session

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def render(request: Request, name: str, context: dict | None = None, status_code: int = 200):
    ctx = {"request": request, **(context or {})}
    template = templates.env.get_template(name)
    return HTMLResponse(template.render(ctx), status_code=status_code)


def get_db():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse("/panel", status_code=303)
    return render(request, "login.html", {"error": None})


@router.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if login_user(request, username.strip(), password):
        return RedirectResponse("/panel", status_code=303)
    return render(request, "login.html", {"error": "Identifiants incorrects"}, status_code=401)


@router.post("/logout")
def logout(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    logout_user(request)
    return RedirectResponse("/login", status_code=303)


@router.get("/panel", response_class=HTMLResponse)
def panel_home(request: Request, db=Depends(get_db)):
    redirect = redirect_if_not_auth(request)
    if redirect:
        return redirect
    jobs = db.query(SessionJob).order_by(SessionJob.created_at.desc()).limit(30).all()
    subjects = list_known_subjects()
    return render(
        request,
        "panel.html",
        {
            "user": request.session.get("ects_user"),
            "jobs": jobs,
            "subjects": subjects,
            "JobStatus": JobStatus,
            "message": request.query_params.get("msg"),
            "error": request.query_params.get("err"),
        },
    )


@router.post("/panel/upload")
async def panel_upload(
    request: Request,
    db=Depends(get_db),
    subject: str = Form(...),
    session_date: str = Form(...),
    files: list[UploadFile] = File(...),
):
    redirect = redirect_if_not_auth(request)
    if redirect:
        return redirect
    try:
        payload = []
        for f in files:
            if not f.filename:
                continue
            payload.append((f.filename, await f.read()))
        job, _ = save_uploaded_session(db, subject, session_date, payload)
        return RedirectResponse(f"/panel?msg=Séance {job.slug} envoyée au pipeline", status_code=303)
    except ValueError as exc:
        return RedirectResponse(f"/panel?err={exc}", status_code=303)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def panel_job_detail(request: Request, job_id: int, db=Depends(get_db)):
    redirect = redirect_if_not_auth(request)
    if redirect:
        return redirect
    job = db.query(SessionJob).filter(SessionJob.id == job_id).first()
    if not job:
        return RedirectResponse("/panel?err=Job introuvable", status_code=303)
    corrections = [c for c in job.corrections if c.status == CorrectionStatus.PENDING]
    return render(
        request,
        "job_detail.html",
        {
            "user": request.session.get("ects_user"),
            "job": job,
            "corrections": corrections,
            "JobStatus": JobStatus,
            "message": request.query_params.get("msg"),
            "error": request.query_params.get("err"),
        },
    )


@router.post("/jobs/{job_id}/approve-review")
def panel_approve_review(request: Request, job_id: int, db=Depends(get_db)):
    redirect = redirect_if_not_auth(request)
    if redirect:
        return redirect
    job = db.query(SessionJob).filter(SessionJob.id == job_id).first()
    if not job or job.status != JobStatus.AWAITING_REVIEW:
        return RedirectResponse(f"/jobs/{job_id}?err=Pas en revue", status_code=303)
    job.status = JobStatus.PENDING
    job.current_step = __import__("app.db.models", fromlist=["JobStep"]).JobStep.GENERATE
    db.commit()
    return RedirectResponse(f"/jobs/{job_id}?msg=Pipeline relancé", status_code=303)


@router.post("/corrections/{correction_id}/decide")
def panel_decide_correction(
    request: Request,
    correction_id: int,
    approved: str = Form(...),
    job_id: int = Form(...),
    db=Depends(get_db),
):
    redirect = redirect_if_not_auth(request)
    if redirect:
        return redirect
    from app.services.review import approve_correction

    approve_correction(db, correction_id, approved.lower() in {"true", "1", "yes", "on"})
    return RedirectResponse(f"/jobs/{job_id}?msg=Correction enregistrée", status_code=303)
