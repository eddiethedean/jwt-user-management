from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from api_test_helpers import load_wrapped_app, seed_unused_invite, seed_user


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
    app = load_wrapped_app(db_url=db_url)

    import app.db as db
    from app.core.config import settings
    from app.core.security import create_access_token

    admin_id = seed_user(
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
    app = load_wrapped_app(db_url=db_url)

    import app.db as db
    from app.core.config import settings

    seed_user(
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
    app = load_wrapped_app(db_url=db_url)

    import app.db as db
    from app.core.security import verify_password
    from app.models import PasswordResetToken, User

    seed_user(
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

    client = TestClient(app, base_url="http://testserver")
    r = client.post("/password/reset", json={"token": raw, "password": "newpassword12"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == "user@example.com")).first()
        assert u
        assert verify_password("newpassword12", u.hashed_password)
        pr = s.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == PasswordResetToken.hash_token(raw)
            )
        ).first()
        assert pr
        assert pr.used_at is not None


def test_password_reset_validation_and_unknown_token(app_client) -> None:
    r = app_client.post("/password/reset", json={"token": "", "password": ""})
    assert r.status_code == 422
    r2 = app_client.post(
        "/password/reset", json={"token": "bad", "password": "longpassword1"}
    )
    assert r2.status_code == 404


def test_password_reset_rejects_password_shorter_than_min(
    app_client, db_engine
) -> None:
    from app.core.security import verify_password
    from app.models import PasswordResetToken, User

    seed_user(
        db_engine=db_engine,
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
    with Session(db_engine) as s:
        rec.expires_at = datetime.now(timezone.utc).replace(year=2099)
        s.add(rec)
        s.commit()

    r = app_client.post("/password/reset", json={"token": raw, "password": "ab"})
    assert r.status_code == 400
    assert "at least" in str(r.json().get("detail", "")).lower()

    with Session(db_engine) as s:
        u = s.exec(select(User).where(User.email == "user@example.com")).first()
        assert u
        assert verify_password("oldpw", u.hashed_password)


def test_inactive_user_bearer_forbidden(app_client, db_engine) -> None:
    from app.core.security import create_access_token

    uid = seed_user(
        db_engine=db_engine,
        email="sleepy@example.com",
        password="pw",
        is_admin=False,
        is_active=False,
    )
    token = create_access_token(subject=str(uid))
    h = {"Authorization": f"Bearer {token}"}
    assert app_client.get("/users/me", headers=h).status_code == 403
    assert app_client.get("/users", headers=h).status_code == 403


def test_inactive_admin_cannot_use_admin_or_invite_endpoints(
    app_client, db_engine
) -> None:
    from app.core.security import create_access_token

    uid = seed_user(
        db_engine=db_engine,
        email="adminoff@example.com",
        password="pw",
        is_admin=True,
        is_active=False,
    )
    token = create_access_token(subject=str(uid))
    h = {"Authorization": f"Bearer {token}"}
    assert (
        app_client.patch(
            "/admin/users/999", headers=h, json={"full_name": "x"}
        ).status_code
        == 403
    )
    assert (
        app_client.post(
            "/invites", headers=h, json={"email": "x@example.com"}
        ).status_code
        == 403
    )


def test_invite_accept_rejects_short_password(app_client, db_engine) -> None:
    raw = seed_unused_invite(db_engine=db_engine, email="inv@example.com")
    r = app_client.post(
        "/invites/accept",
        json={"token": raw, "password": "ab"},
    )
    assert r.status_code == 400
    assert "at least" in str(r.json().get("detail", "")).lower()


def test_invite_email_uses_ui_query_params_when_ui_public_base_set(
    tmp_path, monkeypatch
) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = load_wrapped_app(db_url=db_url)

    import app.db as db
    from app.core.config import settings
    from app.core.security import create_access_token

    settings.ui_public_base_url = "http://127.0.0.1:8502"
    settings.smtp_host = "smtp.test.local"
    settings.smtp_from_email = "noreply@test.local"
    admin_id = seed_user(
        db_engine=db.engine,
        email="admin@example.com",
        password="admin123",
        is_admin=True,
    )
    token = create_access_token(subject=str(admin_id))
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
    assert "page=Accept+invite" in data["invite_url"]
    assert "token=" in data["invite_url"]
    body = _extract_first_text_part(_FakeSMTP.sent[0].msg)
    assert "page=Accept+invite" in body
