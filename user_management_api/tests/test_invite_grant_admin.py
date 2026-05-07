from __future__ import annotations

import importlib
import os
import re
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

    import app.routes.admin as admin_routes

    importlib.reload(admin_routes)

    import app.routes.invites as invites_routes

    importlib.reload(invites_routes)

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


def _extract_invite_token(html: str) -> str:
    m = re.search(r"invites/accept\?token=([^\s\"<]+)", html)
    assert m, "invite token not found in HTML"
    return m.group(1)


def test_invite_checkbox_grants_admin_on_accept_form_flow(tmp_path) -> None:
    prefix = "/s/e886e3c9ab5a7e147ea97/p/testproj"
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url)

    import app.db as db

    _seed_user(
        db_engine=db.engine,
        email="admin@example.com",
        password="admin123",
        is_admin=True,
    )

    client = TestClient(app, base_url="http://testserver", root_path=prefix)

    # Login as admin to get token.
    r_login = client.post(
        f"{prefix}/login",
        data={"email": "admin@example.com", "password": "admin123"},
        follow_redirects=False,
    )
    assert r_login.status_code == 303
    assert r_login.headers["location"] in {"admin", "../admin"}

    # Create an invite that grants admin.
    r_inv = client.post(
        f"{prefix}/admin/invite",
        data={
            "email": "new.admin@example.com",
            "grant_admin": "1",
        },
        follow_redirects=False,
    )
    assert r_inv.status_code == 200
    # Regression: form action must be absolute under Workbench prefix.
    assert f'action="{prefix}/admin/invite"' in r_inv.text
    raw_invite = _extract_invite_token(r_inv.text)

    # Accept invite (HTML form flow).
    r_accept = client.post(
        f"{prefix}/invites/accept-form",
        data={"token": raw_invite, "password": "NewPassw0rd!123"},
        follow_redirects=False,
    )
    assert r_accept.status_code == 303

    # Regression: invited admin can log in and access /admin (previously gated by SEED_ADMIN_EMAIL).
    r_admin_login = client.post(
        f"{prefix}/login",
        data={"email": "new.admin@example.com", "password": "NewPassw0rd!123"},
        follow_redirects=False,
    )
    assert r_admin_login.status_code == 303
    assert r_admin_login.headers["location"] in {"admin", "../admin"}

    r_admin = client.get(f"{prefix}/admin")
    assert r_admin.status_code == 200

    from app.models import User

    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == "new.admin@example.com")).first()
        assert u
        assert u.is_admin is True


def test_invite_without_checkbox_does_not_grant_admin(tmp_path) -> None:
    prefix = "/s/e886e3c9ab5a7e147ea97/p/testproj"
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url)

    import app.db as db

    _seed_user(
        db_engine=db.engine,
        email="admin@example.com",
        password="admin123",
        is_admin=True,
    )

    client = TestClient(app, base_url="http://testserver", root_path=prefix)

    r_login = client.post(
        f"{prefix}/login",
        data={"email": "admin@example.com", "password": "admin123"},
        follow_redirects=False,
    )
    assert r_login.status_code == 303
    assert r_login.headers["location"] in {"admin", "../admin"}

    r_inv = client.post(
        f"{prefix}/admin/invite",
        data={"email": "regular.user@example.com"},
        follow_redirects=False,
    )
    assert r_inv.status_code == 200
    raw_invite = _extract_invite_token(r_inv.text)

    r_accept = client.post(
        f"{prefix}/invites/accept-form",
        data={"token": raw_invite, "password": "NewPassw0rd!123"},
        follow_redirects=False,
    )
    assert r_accept.status_code == 303

    from app.models import User

    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.email == "regular.user@example.com")).first()
        assert u
        assert u.is_admin is False


def test_non_admin_cannot_create_invite_api(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url)

    import app.db as db
    from app.core.security import create_access_token

    user_id = _seed_user(
        db_engine=db.engine, email="user@example.com", password="pw", is_admin=False
    )
    token = create_access_token(subject=str(user_id))

    client = TestClient(app, base_url="http://testserver")
    r = client.post(
        "/invites",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "x@example.com", "grant_admin": True},
    )
    assert r.status_code == 403
