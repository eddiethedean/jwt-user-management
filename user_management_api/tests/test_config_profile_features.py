from __future__ import annotations

import importlib
import sys
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from test_directory_lookup import _Resp, _load_wrapped_app, _seed_admin


def _patch_config(monkeypatch, **attrs: object) -> None:
    import app.core.config as config_mod

    for key, value in attrs.items():
        monkeypatch.setattr(config_mod._defaults, key, value)
    config_mod.refresh_settings()


def _reload_directory(monkeypatch, profile: str) -> None:
    _patch_config(monkeypatch, DIRECTORY_ATTRIBUTE_PROFILE=profile)
    if "app.services.directory" in sys.modules:
        importlib.reload(sys.modules["app.services.directory"])


def test_extended_directory_profile_maps_attributes(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    _load_wrapped_app(db_url=db_url)
    _reload_directory(monkeypatch, "extended")

    import app.services.directory as directory

    monkeypatch.setattr(
        directory.httpx,
        "get",
        lambda *a, **k: _Resp(
            status_code=200,
            json_data={
                "attributes": {
                    "mail": ["user@corp.example.com"],
                    "givenName": ["Jane"],
                    "sn": ["Doe"],
                    "extensionAttribute8": ["US"],
                    "department": ["Operations"],
                }
            },
        ),
    )

    rec = directory.lookup_email("user@corp.example.com")
    assert rec
    assert rec.display_name == "Jane Doe"
    assert rec.country == "US"
    assert rec.command is None


def test_both_directory_profile_prefers_extended_then_generic(
    tmp_path, monkeypatch
) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    _load_wrapped_app(db_url=db_url)
    _reload_directory(monkeypatch, "both")

    import app.services.directory as directory

    monkeypatch.setattr(
        directory.httpx,
        "get",
        lambda *a, **k: _Resp(
            status_code=200,
            json_data={
                "attributes": {
                    "mail": ["user@example.com"],
                    "displayName": ["Display Only"],
                    "co": ["DE"],
                }
            },
        ),
    )

    rec = directory.lookup_email("user@example.com")
    assert rec
    assert rec.display_name == "Display Only"
    assert rec.country == "DE"


def test_extended_directory_includes_command_when_enabled(
    tmp_path, monkeypatch
) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    _load_wrapped_app(db_url=db_url)
    _patch_config(
        monkeypatch,
        DIRECTORY_ATTRIBUTE_PROFILE="extended",
        USER_COMMAND_FIELD_ENABLED=True,
    )
    import app.services.directory as directory

    importlib.reload(directory)

    monkeypatch.setattr(
        directory.httpx,
        "get",
        lambda *a, **k: _Resp(
            status_code=200,
            json_data={
                "attributes": {
                    "mail": ["user@corp.example.com"],
                    "department": ["Operations"],
                }
            },
        ),
    )

    rec = directory.lookup_email("user@corp.example.com")
    assert rec and rec.command == "Operations"


def test_registration_rejects_missing_directory_when_required(
    tmp_path, monkeypatch
) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url, enable_directory=True)

    _patch_config(
        monkeypatch,
        REGISTRATION_DIRECTORY_LOOKUP_ENABLED=True,
        REGISTRATION_DIRECTORY_LOOKUP_REQUIRED=True,
        REGISTRATION_DIRECTORY_LOOKUP_SUFFIXES=("example.com",),
    )

    import app.services.directory as directory

    monkeypatch.setattr(directory.httpx, "get", lambda *a, **k: _Resp(status_code=404))

    client = TestClient(app, base_url="http://testserver")
    r = client.post("/register", data={"email": "new@example.com"})
    assert r.status_code == 400
    assert "directory" in (r.json().get("detail") or "").lower()

    r2 = client.post("/register", data={"email": "new@example.org"})
    assert r2.status_code == 200


def test_registration_allowed_when_directory_returns_record(
    tmp_path, monkeypatch
) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url, enable_directory=True)

    _patch_config(
        monkeypatch,
        REGISTRATION_DIRECTORY_LOOKUP_ENABLED=True,
        REGISTRATION_DIRECTORY_LOOKUP_REQUIRED=True,
        REGISTRATION_DIRECTORY_LOOKUP_SUFFIXES=("example.com",),
    )

    import app.services.directory as directory

    monkeypatch.setattr(
        directory.httpx,
        "get",
        lambda *a, **k: _Resp(
            status_code=200,
            json_data={"attributes": {"mail": ["new@example.com"], "co": ["US"]}},
        ),
    )

    client = TestClient(app, base_url="http://testserver")
    r = client.post("/register", data={"email": "new@example.com"})
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_invite_lookup_returns_command_when_enabled(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url, enable_directory=True)

    import app.db as db

    _seed_admin(db_engine=db.engine)
    _patch_config(
        monkeypatch,
        USER_COMMAND_FIELD_ENABLED=True,
        DIRECTORY_ATTRIBUTE_PROFILE="extended",
    )

    import app.services.directory as directory

    importlib.reload(directory)
    monkeypatch.setattr(
        directory.httpx,
        "get",
        lambda *a, **k: _Resp(
            status_code=200,
            json_data={
                "attributes": {
                    "mail": ["target@example.com"],
                    "department": ["Ops"],
                }
            },
        ),
    )

    client = TestClient(app, base_url="http://testserver")
    token_r = client.post(
        "/auth/token",
        data={"username": "admin@example.com", "password": "admin123"},
    )
    token = token_r.json()["access_token"]
    r = client.post(
        "/invites/lookup",
        json={"email": "target@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["command"] == "Ops"
    assert body["display_name"] == ""


def test_invite_accept_stores_command_when_enabled(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url, enable_directory=False)

    _patch_config(
        monkeypatch,
        USER_COMMAND_FIELD_ENABLED=True,
        INVITE_ACCEPT_DIRECTORY_ENRICH=False,
    )

    import app.db as db
    from app.models import InviteToken, User

    raw = InviteToken.new_raw_token()
    invite = InviteToken(
        email="user@example.com",
        token_hash=InviteToken.hash_token(raw),
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc).replace(year=2099),
        used_at=None,
        grant_admin=False,
    )
    with Session(db.engine) as s:
        s.add(invite)
        s.commit()

    client = TestClient(app, base_url="http://testserver")
    r = client.post(
        "/invites/accept",
        json={"token": raw, "password": "longpassword", "command": "Operations"},
    )
    assert r.status_code == 200

    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == "user@example.com")).first()
        assert u and u.command == "Operations"


def test_invite_accept_enriches_country_from_directory(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url, enable_directory=True)

    _patch_config(monkeypatch, INVITE_ACCEPT_DIRECTORY_ENRICH=True)

    import app.db as db
    import app.services.directory as directory
    from app.models import InviteToken, User

    raw = InviteToken.new_raw_token()
    invite = InviteToken(
        email="user@example.com",
        token_hash=InviteToken.hash_token(raw),
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc).replace(year=2099),
        used_at=None,
        grant_admin=False,
    )
    with Session(db.engine) as s:
        s.add(invite)
        s.commit()

    monkeypatch.setattr(
        directory.httpx,
        "get",
        lambda *a, **k: _Resp(
            status_code=200,
            json_data={"attributes": {"mail": ["user@example.com"], "co": ["US"]}},
        ),
    )

    client = TestClient(app, base_url="http://testserver")
    r = client.post(
        "/invites/accept",
        json={"token": raw, "password": "longpassword"},
    )
    assert r.status_code == 200

    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == "user@example.com")).first()
        assert u and u.country == "US"


def test_invite_accept_ignores_body_profile_when_overrides_disabled(
    tmp_path, monkeypatch
) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url, enable_directory=False)

    _patch_config(
        monkeypatch,
        USER_COMMAND_FIELD_ENABLED=True,
        INVITE_ACCEPT_ALLOW_PROFILE_OVERRIDES=False,
        INVITE_ACCEPT_DIRECTORY_ENRICH=False,
    )

    import app.db as db
    from app.models import InviteToken, User

    raw = InviteToken.new_raw_token()
    with Session(db.engine) as s:
        s.add(
            InviteToken(
                email="user@example.com",
                token_hash=InviteToken.hash_token(raw),
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc).replace(year=2099),
                used_at=None,
                grant_admin=False,
            )
        )
        s.commit()

    client = TestClient(app, base_url="http://testserver")
    r = client.post(
        "/invites/accept",
        json={
            "token": raw,
            "password": "longpassword",
            "full_name": "Ignored",
            "country": "ZZ",
            "command": "Ignored",
        },
    )
    assert r.status_code == 200

    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == "user@example.com")).first()
        assert u
        assert u.full_name is None
        assert u.country is None
        assert u.command is None


def test_users_me_and_admin_patch_command(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url, enable_directory=False)

    import app.db as db
    from app.core.security import hash_password
    from app.models import User

    with Session(db.engine) as s:
        s.add(
            User(
                email="user@example.com",
                hashed_password=hash_password("password"),
                is_admin=False,
                created_at=datetime.now(timezone.utc),
            )
        )
        s.add(
            User(
                email="admin@example.com",
                hashed_password=hash_password("admin123"),
                is_admin=True,
                created_at=datetime.now(timezone.utc),
            )
        )
        s.commit()

    _patch_config(monkeypatch, USER_COMMAND_FIELD_ENABLED=True)

    client = TestClient(app, base_url="http://testserver")
    token = client.post(
        "/auth/token",
        data={"username": "user@example.com", "password": "password"},
    ).json()["access_token"]

    me = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert "command" in me.json()

    admin_token = client.post(
        "/auth/token",
        data={"username": "admin@example.com", "password": "admin123"},
    ).json()["access_token"]

    with Session(db.engine) as s:
        user = s.exec(select(User).where(User.email == "user@example.com")).first()
        assert user is not None
        uid = user.id

    patched = client.patch(
        f"/admin/users/{uid}",
        json={"command": "Updated"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert patched.status_code == 200
    assert patched.json()["user"]["command"] == "Updated"


def test_min_password_length_from_config(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url, enable_directory=False)

    _patch_config(monkeypatch, MIN_PASSWORD_LENGTH=8)

    import app.db as db
    from app.models import InviteToken

    raw = InviteToken.new_raw_token()
    with Session(db.engine) as s:
        s.add(
            InviteToken(
                email="user@example.com",
                token_hash=InviteToken.hash_token(raw),
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc).replace(year=2099),
                used_at=None,
                grant_admin=False,
            )
        )
        s.commit()

    client = TestClient(app, base_url="http://testserver")
    short = client.post("/invites/accept", json={"token": raw, "password": "short"})
    assert short.status_code == 400
    assert "8" in (short.json().get("detail") or "")

    ok = client.post(
        "/invites/accept",
        json={"token": raw, "password": "longenough"},
    )
    assert ok.status_code == 200
