from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

from fluxlit.testing import FluxLitTestClient
from sqlmodel import Session, select

from conftest import load_fluxlit_app


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
    if msg.get_content_type() == "text/plain":
        return msg.get_content()
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            return part.get_content()
    return ""


def test_invite_api_sends_email_when_smtp_configured(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_fluxlit_app(db_url=db_url)

    import app.db as db
    from app.core.config import settings
    from app.core.security import create_access_token

    admin_id = _seed_user(
        db_engine=db.engine,
        email="admin@example.com",
        password="admin123",
        is_admin=True,
    )
    token = create_access_token(subject=str(admin_id))

    settings.smtp_host = "smtp.test.local"
    settings.smtp_from_email = "noreply@test.local"
    monkeypatch.setattr("app.services.email.smtplib.SMTP", _FakeSMTP)
    _FakeSMTP.sent.clear()

    tc = FluxLitTestClient(app)
    r = tc.api_post(
        "/invites",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "new.user@example.com", "grant_admin": False},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "/?page=Accept+invite&token=" in data["invite_url"]
    assert len(_FakeSMTP.sent) == 1
    msg = _FakeSMTP.sent[0].msg
    assert msg["To"] == "new.user@example.com"
    assert msg["From"] == "noreply@test.local"
    body = _extract_first_text_part(msg)
    assert "Accept invite:" in body


def test_invite_email_uses_fluxlit_public_base_url_when_set(
    tmp_path, monkeypatch
) -> None:
    db_url = f"sqlite:///{tmp_path / 'fluxlit_public.db'}"
    app = load_fluxlit_app(
        db_url=db_url,
        extra_env={
            "FLUXLIT_PUBLIC_BASE_URL": "https://workbench.example.org/my-app",
            "PUBLIC_BASE_URL": "http://127.0.0.1:8000",
        },
    )

    import app.db as db
    from app.core.config import settings
    from app.core.security import create_access_token

    admin_id = _seed_user(
        db_engine=db.engine,
        email="admin@example.com",
        password="admin123",
        is_admin=True,
    )
    token = create_access_token(subject=str(admin_id))

    settings.smtp_host = "smtp.test.local"
    settings.smtp_from_email = "noreply@test.local"
    monkeypatch.setattr("app.services.email.smtplib.SMTP", _FakeSMTP)
    _FakeSMTP.sent.clear()

    tc = FluxLitTestClient(app)
    r = tc.api_post(
        "/invites",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "new.user@example.com", "grant_admin": False},
    )
    assert r.status_code == 200
    body = _extract_first_text_part(_FakeSMTP.sent[0].msg)
    assert "https://workbench.example.org/my-app/?page=" in body
    assert "127.0.0.1" not in body


def test_invite_email_fluxlit_public_base_avoids_duplicate_mount(
    tmp_path, monkeypatch
) -> None:
    """When FLUXLIT_PUBLIC_BASE_URL already ends with ASGI root_path, do not prefix twice."""
    from starlette.testclient import TestClient

    db_url = f"sqlite:///{tmp_path / 'dup_mount.db'}"
    app = load_fluxlit_app(
        db_url=db_url,
        extra_env={
            "FLUXLIT_PUBLIC_BASE_URL": "https://workbench.example.org/prefix/app",
        },
    )

    import app.db as db
    from app.core.config import settings
    from app.core.security import create_access_token

    admin_id = _seed_user(
        db_engine=db.engine,
        email="admin2@example.com",
        password="admin123",
        is_admin=True,
    )
    token = create_access_token(subject=str(admin_id))

    settings.smtp_host = "smtp.test.local"
    settings.smtp_from_email = "noreply@test.local"
    monkeypatch.setattr("app.services.email.smtplib.SMTP", _FakeSMTP)
    _FakeSMTP.sent.clear()

    client = TestClient(
        app.api, base_url="http://internal.test", root_path="/prefix/app"
    )
    r = client.post(
        "/invites",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "mount.user@example.com", "grant_admin": False},
    )
    assert r.status_code == 200
    body = _extract_first_text_part(_FakeSMTP.sent[0].msg)
    assert "https://workbench.example.org/prefix/app/?page=" in body
    assert "/prefix/app/prefix/app" not in body


def test_password_forgot_is_non_enumerating_and_emails_if_user_exists(
    tmp_path, monkeypatch
) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_fluxlit_app(db_url=db_url)

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

    tc = FluxLitTestClient(app)

    r_missing = tc.api_post("/password/forgot", json={"email": "missing@example.com"})
    assert r_missing.status_code == 200
    assert r_missing.json() == {"ok": True}
    assert len(_FakeSMTP.sent) == 0

    r_exists = tc.api_post("/password/forgot", json={"email": "user@example.com"})
    assert r_exists.status_code == 200
    assert r_exists.json() == {"ok": True}
    assert len(_FakeSMTP.sent) == 1
    msg = _FakeSMTP.sent[0].msg
    assert msg["To"] == "user@example.com"
    assert "Password reset" in (msg["Subject"] or "")
    body = _extract_first_text_part(msg)
    assert "/?page=Reset+password&token=" in body


def test_password_reset_api_updates_password_and_marks_token_used(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_fluxlit_app(db_url=db_url)

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
        rec.expires_at = datetime.now(timezone.utc).replace(year=2099)
        s.add(rec)
        s.commit()

    tc = FluxLitTestClient(app)
    r = tc.api_post("/password/reset", json={"token": raw, "password": "newpassword"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == "user@example.com")).first()
        assert u
        assert verify_password("newpassword", u.hashed_password)
        pr = s.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == PasswordResetToken.hash_token(raw)
            )
        ).first()
        assert pr
        assert pr.used_at is not None


def test_password_reset_api_errors(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_fluxlit_app(db_url=db_url)

    tc = FluxLitTestClient(app)
    r = tc.api_post("/password/reset", json={"token": "", "password": ""})
    assert r.status_code == 422
    r2 = tc.api_post("/password/reset", json={"token": "bad", "password": "validpass"})
    assert r2.status_code == 404


def test_password_reset_rejects_short_password(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_fluxlit_app(db_url=db_url)

    import app.db as db
    from app.models import PasswordResetToken

    raw = PasswordResetToken.new_raw_token()
    rec = PasswordResetToken(
        email="user@example.com",
        token_hash=PasswordResetToken.hash_token(raw),
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc).replace(year=2099),
        used_at=None,
    )
    with Session(db.engine) as s:
        s.add(rec)
        s.commit()

    tc = FluxLitTestClient(app)
    r = tc.api_post("/password/reset", json={"token": raw, "password": "short"})
    assert r.status_code == 400
    assert "at least 8" in str(r.json().get("detail", ""))


def test_invite_accept_rejects_short_password(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_fluxlit_app(db_url=db_url)

    import app.db as db
    from app.models import InviteToken

    raw = InviteToken.new_raw_token()
    rec = InviteToken(
        email="invited@example.com",
        token_hash=InviteToken.hash_token(raw),
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc).replace(year=2099),
        used_at=None,
        grant_admin=False,
    )
    with Session(db.engine) as s:
        s.add(rec)
        s.commit()

    tc = FluxLitTestClient(app)
    r = tc.api_post("/invites/accept", json={"token": raw, "password": "short"})
    assert r.status_code == 400
    assert "at least 8" in str(r.json().get("detail", ""))
