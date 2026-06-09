from __future__ import annotations

import concurrent.futures

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from test_directory_lookup import _load_wrapped_app, _seed_admin
from test_email_invites_and_password_reset import _seed_user


def test_non_admin_cannot_list_users_json(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url)
    import app.db as db
    from app.auth.jwt_principal import access_token_extra_claims_for_user
    from app.core.security import create_access_token
    from app.models import User

    uid = _seed_user(
        db_engine=db.engine,
        email="user@example.com",
        password="pw",
        is_admin=False,
    )
    with Session(db.engine) as s:
        user = s.get(User, uid)
        assert user
        token = create_access_token(
            subject=str(uid), extra_claims=access_token_extra_claims_for_user(user)
        )
    client = TestClient(app, base_url="http://testserver")
    r = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_directory_lookup_rejects_mail_mismatch(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    _load_wrapped_app(db_url=db_url)
    import app.services.directory as directory

    class _Resp:
        status_code = 200

        def json(self):
            return {
                "attributes": {
                    "mail": ["other@example.com"],
                    "co": ["US"],
                }
            }

    monkeypatch.setattr(directory.httpx, "get", lambda *a, **k: _Resp())
    assert directory.lookup_email("user@example.com") is None


def test_concurrent_invite_accept_only_one_succeeds(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url)
    import app.db as db

    _seed_admin(db_engine=db.engine)
    client = TestClient(app, base_url="http://testserver")
    from app.auth.jwt_principal import access_token_extra_claims_for_user
    from app.core.security import create_access_token
    from app.models import User

    with Session(db.engine) as s:
        admin = s.exec(select(User).where(User.email == "admin@example.com")).first()
        assert admin
        token = create_access_token(
            subject=str(admin.id),
            extra_claims=access_token_extra_claims_for_user(admin),
        )
    inv = client.post(
        "/invites",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "newuser@example.com"},
    )
    assert inv.status_code == 200
    raw = inv.json()["invite_url"].split("token=")[-1]

    def _accept() -> int:
        c = TestClient(app, base_url="http://testserver")
        return c.post(
            "/invites/accept",
            json={"token": raw, "password": "password123"},
        ).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda _: _accept(), range(2)))

    assert codes.count(200) == 1
    assert 400 in codes or 404 in codes
