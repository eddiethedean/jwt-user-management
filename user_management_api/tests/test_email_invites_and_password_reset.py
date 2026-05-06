from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from typing import Any, List

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select
from starlette.types import ASGIApp


def _load_wrapped_app(*, db_url: str) -> ASGIApp:
    """
    Load the backend ASGI app wrapped by the Workbench adapter (app.asgi:app),
    reloading modules that read settings at import time.
    """
    os.environ["DATABASE_URL"] = db_url
    os.environ["JWT_SECRET"] = "test-secret"

    SQLModel.metadata.clear()
    import sqlmodel.main as sqlmodel_main

    sqlmodel_main.default_registry.dispose()

    for k in list(sys.modules.keys()):
        if k == "app" or k.startswith("app."):
            sys.modules.pop(k, None)

    here = os.path.dirname(__file__)
    api_root = os.path.abspath(os.path.join(here, ".."))
    if api_root not in sys.path:
        sys.path.insert(0, api_root)

    app_pkg_dir = os.path.join(api_root, "app")
    app_init = os.path.join(app_pkg_dir, "__init__.py")
    spec = spec_from_file_location(
        "app", app_init, submodule_search_locations=[app_pkg_dir]
    )
    assert spec and spec.loader
    app_pkg = module_from_spec(spec)
    sys.modules["app"] = app_pkg
    spec.loader.exec_module(app_pkg)

    import app.core.config as config

    importlib.reload(config)

    import app.db as db

    importlib.reload(db)

    import app.core.security as security

    importlib.reload(security)

    import app.services.email as email_service

    importlib.reload(email_service)

    import app.routes.admin as admin_routes

    importlib.reload(admin_routes)

    import app.routes.invites as invites_routes

    importlib.reload(invites_routes)

    import app.routes.password_reset as password_reset_routes

    importlib.reload(password_reset_routes)

    import app.main as main

    importlib.reload(main)

    import app.asgi as asgi

    importlib.reload(asgi)

    SQLModel.metadata.create_all(db.engine)
    return asgi.app  # type: ignore[return-value]


def _seed_user(*, db_engine, email: str, password: str, is_admin: bool) -> int:
    from app.core.security import hash_password
    from app.models import User

    with Session(db_engine) as s:
        u = User(
            email=email,
            hashed_password=hash_password(password),
            is_admin=is_admin,
            created_at=datetime.now(timezone.utc),
        )
        s.add(u)
        s.commit()
        s.refresh(u)
        assert u.id is not None
        return int(u.id)


class _Sent:
    def __init__(self, msg: Any):
        self.msg = msg


class _FakeSMTP:
    sent: List[_Sent] = []

    def __init__(self, host: str, port: int | None = None):  # noqa: ARG002
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ARG002
        self.quit()

    def starttls(self) -> None:
        return None

    def login(self, username: str, password: str) -> None:  # noqa: ARG002
        return None

    def send_message(self, msg) -> None:
        self.sent.append(_Sent(msg))

    def quit(self) -> None:
        self._closed = True


def _extract_first_text_part(msg) -> str:
    """
    Our emails are multipart/alternative (text + html). Extract the text/plain part
    for assertions.
    """
    if msg.get_content_type() == "text/plain":
        return msg.get_content()
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            return part.get_content()
    return ""


def test_invite_api_sends_email_when_smtp_configured(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url)

    import app.db as db
    from app.core.security import create_access_token
    from app.core.config import settings

    admin_id = _seed_user(
        db_engine=db.engine,
        email="admin@example.com",
        password="admin123",
        is_admin=True,
    )
    token = create_access_token(subject=str(admin_id))

    # Configure SMTP and patch smtplib.
    settings.smtp_host = "smtp.test.local"
    settings.smtp_from_email = "noreply@test.local"
    monkeypatch.setattr("app.services.email.smtplib.SMTP", _FakeSMTP)
    _FakeSMTP.sent.clear()

    client = TestClient(app, base_url="http://testserver")
    r = client.post(
        "/invites",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "new.user@example.com", "grant_admin": False},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "/invites/accept?token=" in data["invite_url"]
    assert len(_FakeSMTP.sent) == 1
    msg = _FakeSMTP.sent[0].msg
    assert msg["To"] == "new.user@example.com"
    assert msg["From"] == "noreply@test.local"
    body = _extract_first_text_part(msg)
    assert "Accept invite:" in body


def test_password_forgot_is_non_enumerating_and_emails_if_user_exists(
    tmp_path, monkeypatch
) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url)

    import app.db as db
    from app.core.config import settings

    _ = _seed_user(
        db_engine=db.engine,
        email="user@example.com",
        password="pw",
        is_admin=False,
    )

    settings.smtp_host = "smtp.test.local"
    settings.smtp_from_email = "noreply@test.local"
    settings.smtp_use_tls = True
    settings.smtp_port = 587
    monkeypatch.setattr("app.services.email.smtplib.SMTP", _FakeSMTP)
    _FakeSMTP.sent.clear()

    client = TestClient(app, base_url="http://testserver")

    r_missing = client.post("/password/forgot", json={"email": "missing@example.com"})
    assert r_missing.status_code == 200
    assert r_missing.json() == {"ok": True}
    assert len(_FakeSMTP.sent) == 0

    r_exists = client.post("/password/forgot", json={"email": "user@example.com"})
    assert r_exists.status_code == 200
    assert r_exists.json() == {"ok": True}
    assert len(_FakeSMTP.sent) == 1
    msg = _FakeSMTP.sent[0].msg
    assert msg["To"] == "user@example.com"
    assert "Password reset" in (msg["Subject"] or "")
    body = _extract_first_text_part(msg)
    assert "/password/reset?token=" in body


def test_password_reset_api_updates_password_and_marks_token_used(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url)

    import app.db as db
    from app.core.security import verify_password
    from app.models import PasswordResetToken, User

    _ = _seed_user(
        db_engine=db.engine,
        email="user@example.com",
        password="oldpw",
        is_admin=False,
    )

    raw = PasswordResetToken.new_raw_token()
    rec = PasswordResetToken(
        email="user@example.com",
        token_hash=PasswordResetToken.hash_token(raw),
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
        used_at=None,
    )
    with Session(db.engine) as s:
        # Make it valid for a bit by extending expiry.
        rec.expires_at = datetime.now(timezone.utc).replace(year=2099)
        s.add(rec)
        s.commit()

    client = TestClient(app, base_url="http://testserver")
    r = client.post("/password/reset", json={"token": raw, "password": "newpw"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == "user@example.com")).first()
        assert u
        assert verify_password("newpw", u.hashed_password)
        pr = s.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == PasswordResetToken.hash_token(raw)
            )
        ).first()
        assert pr
        assert pr.used_at is not None


def test_password_reset_api_errors(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url)

    client = TestClient(app, base_url="http://testserver")
    r = client.post("/password/reset", json={"token": "", "password": ""})
    assert r.status_code == 422
    r2 = client.post("/password/reset", json={"token": "bad", "password": "pw"})
    assert r2.status_code == 404
