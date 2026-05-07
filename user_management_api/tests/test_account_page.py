from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select
from starlette.types import ASGIApp


def _load_wrapped_app(*, db_url: str) -> ASGIApp:
    os.environ["DATABASE_URL"] = db_url
    os.environ["JWT_SECRET"] = "test-secret"
    os.environ.pop("DIRECTORY_LOOKUP_URL", None)
    os.environ.pop("DIRECTORY_LOOKUP_TIMEOUT_S", None)
    os.environ.pop("DIRECTORY_LOOKUP_REQUIRED", None)

    # Avoid SQLAlchemy table/class redefinition issues across reloads.
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

    import app.routes.account as account_routes

    importlib.reload(account_routes)

    import app.routes.auth as auth_routes

    importlib.reload(auth_routes)

    import app.routes.users as users_routes

    importlib.reload(users_routes)

    import app.main as main

    importlib.reload(main)

    import app.asgi as asgi

    importlib.reload(asgi)

    SQLModel.metadata.create_all(db.engine)
    return asgi.app  # type: ignore[return-value]


def _seed_user(*, db_engine, email: str, password: str, full_name: str | None = None) -> int:
    from app.core.security import hash_password
    from app.models import User

    with Session(db_engine) as s:
        u = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            is_admin=False,
            created_at=datetime.now(timezone.utc),
        )
        s.add(u)
        s.commit()
        s.refresh(u)
        assert u.id is not None
        return int(u.id)


def test_account_page_shows_info_and_updates_name_and_password(tmp_path) -> None:
    prefix = "/s/e886e3c9ab5a7e147ea97/p/testproj"
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url)

    import app.db as db
    from app.models import User

    user_id = _seed_user(
        db_engine=db.engine,
        email="user@example.com",
        password="oldpassword",
        full_name=None,
    )

    client = TestClient(app, base_url="http://testserver", root_path=prefix)

    # Not logged in -> /account redirects to login with msg + next.
    r0 = client.get(f"{prefix}/account", follow_redirects=False)
    assert r0.status_code == 303
    assert r0.headers["location"].startswith("login?msg=")
    assert "next=%2Faccount" in r0.headers["location"] or "next=/account" in r0.headers["location"]

    # Login creates cookie and redirects to users.
    r_login = client.post(
        f"{prefix}/login",
        data={"email": "user@example.com", "password": "oldpassword"},
        follow_redirects=False,
    )
    assert r_login.status_code == 303
    assert r_login.headers["location"] in {"users", "../users"}

    # Users page should show global session pill with Account link.
    r_users = client.get(f"{prefix}/users")
    assert r_users.status_code == 200
    assert "Signed in as" in r_users.text
    assert "user@example.com" in r_users.text
    assert f'href="{prefix}/account"' in r_users.text

    # Account page shows info.
    r1 = client.get(f"{prefix}/account")
    assert r1.status_code == 200
    assert "<h2" in r1.text and "Account" in r1.text
    assert "user@example.com" in r1.text

    # Update name.
    r2 = client.post(
        f"{prefix}/account",
        data={"full_name": "Test User"},
        follow_redirects=False,
    )
    assert r2.status_code == 200
    assert "Saved." in r2.text
    assert "Test User" in r2.text

    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.id == user_id)).first()
        assert u
        assert u.full_name == "Test User"

    # Wrong current password.
    r_bad = client.post(
        f"{prefix}/account/password",
        data={
            "current_password": "wrong",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123",
        },
        follow_redirects=False,
    )
    assert r_bad.status_code == 400
    assert "Current password is incorrect." in r_bad.text

    # Password mismatch.
    r_mismatch = client.post(
        f"{prefix}/account/password",
        data={
            "current_password": "oldpassword",
            "new_password": "newpassword123",
            "confirm_password": "different",
        },
        follow_redirects=False,
    )
    assert r_mismatch.status_code == 400
    assert "do not match" in r_mismatch.text

    # Too short.
    r_short = client.post(
        f"{prefix}/account/password",
        data={
            "current_password": "oldpassword",
            "new_password": "short",
            "confirm_password": "short",
        },
        follow_redirects=False,
    )
    assert r_short.status_code == 400
    assert "at least 8 characters" in r_short.text

    # Success.
    r_ok = client.post(
        f"{prefix}/account/password",
        data={
            "current_password": "oldpassword",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123",
        },
        follow_redirects=False,
    )
    assert r_ok.status_code == 200
    assert "Password updated." in r_ok.text

    # Old password no longer works; new one does.
    client2 = TestClient(app, base_url="http://testserver", root_path=prefix)
    r_old = client2.post(
        f"{prefix}/login",
        data={"email": "user@example.com", "password": "oldpassword"},
        follow_redirects=False,
    )
    assert r_old.status_code == 400
    assert "Invalid email or password" in r_old.text

    r_new = client2.post(
        f"{prefix}/login",
        data={"email": "user@example.com", "password": "newpassword123"},
        follow_redirects=False,
    )
    assert r_new.status_code == 303
    assert r_new.headers["location"] in {"users", "../users"}

