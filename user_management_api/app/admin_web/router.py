from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from starlette.requests import Request
from starlette.responses import Response

from app.admin_web.auth import get_admin_session_user_id, require_admin_session
from app.admin_web.csrf import get_csrf_token, require_csrf, validate_csrf
from app.api.deps import get_db
from app.core.config import settings
from app.core.security import verify_password
from app.models.user import User


templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)

router = APIRouter(prefix="/admin", tags=["admin-web"])


def _base_path(request: Request) -> str:
    # Prefer configured BASE_PATH when set. Some proxies (Workbench) populate scope.root_path
    # with a URL-like value, and sometimes root_path may be empty even when BASE_PATH is
    # correctly configured.
    if settings.base_path:
        return str(settings.base_path).rstrip("/")

    rp = str(request.scope.get("root_path") or "").strip()
    lowered = rp.lower()
    if "://" in lowered or lowered.startswith("http") or lowered.startswith("https"):
        rp = ""
    return str(rp or "").rstrip("/")


def _admin_url(request: Request, path: str) -> str:
    bp = _base_path(request)
    if not path.startswith("/"):
        path = "/" + path
    return f"{bp}{path}"


@router.get("", include_in_schema=False)
def admin_no_slash(request: Request) -> Response:
    # Avoid Starlette's automatic slash-redirect using request.url (which can be malformed
    # under some proxy setups). We generate a safe relative Location ourselves.
    return RedirectResponse(url=_admin_url(request, "/admin/"), status_code=307)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "admin/login.html",
        {"csrf_token": get_csrf_token(request), "base_path": _base_path(request)},
    )


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    csrf_token: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    try:
        validate_csrf(request, csrf_token)
    except Exception:
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {
                "error": "CSRF failed",
                "csrf_token": get_csrf_token(request),
                "base_path": _base_path(request),
            },
            status_code=403,
        )
    user: User | None = db.exec(select(User).where(User.email == email)).first()
    if (
        not user
        or not user.is_active
        or not user.is_admin
        or not verify_password(password, user.hashed_password)
    ):
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {
                "error": "Invalid email or password",
                "csrf_token": get_csrf_token(request),
                "base_path": _base_path(request),
            },
            status_code=400,
        )
    request.session["admin_user_id"] = user.id  # type: ignore[attr-defined]
    get_csrf_token(request)
    return RedirectResponse(url=_admin_url(request, "/admin/"), status_code=303)


@router.post("/logout")
def logout_submit(
    request: Request,
    _admin: User = Depends(require_admin_session),
    _csrf: None = Depends(require_csrf),
) -> dict:
    request.session.clear()  # type: ignore[attr-defined]
    return {"ok": True}


@router.get("/", response_class=HTMLResponse)
def index_page(request: Request, db: Session = Depends(get_db)) -> Response:
    if not get_admin_session_user_id(request):
        return RedirectResponse(
            url=_admin_url(request, "/admin/login"), status_code=303
        )
    # Validate admin exists/is active.
    require_admin_session(request=request, db=db)
    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {"csrf_token": get_csrf_token(request), "base_path": _base_path(request)},
    )
