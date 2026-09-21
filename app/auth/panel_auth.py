import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from starlette.responses import RedirectResponse

from app.config import get_settings


def _session_secret() -> str:
    settings = get_settings()
    return settings.ects_panel_secret or settings.ects_api_token


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("ects_user"))


def require_panel_user(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Login required")
    return request.session.get("ects_user")


PanelUser = Annotated[str, Depends(require_panel_user)]


def login_user(request: Request, username: str, password: str) -> bool:
    settings = get_settings()
    if not secrets.compare_digest(username, settings.ects_panel_user):
        return False
    if not secrets.compare_digest(password, settings.ects_panel_password):
        return False
    request.session["ects_user"] = username
    return True


def logout_user(request: Request):
    request.session.clear()


def redirect_if_not_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return None
