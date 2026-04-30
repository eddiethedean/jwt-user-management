from __future__ import annotations

import importlib
import os
import sys
import uuid
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select
from starlette.types import ASGIApp


def _load_wrapped_app(*, db_url: str) -> ASGIApp:
    os.environ["DATABASE_URL"] = db_url
    os.environ["JWT_SECRET"] = "test-secret"

    SQLModel.metadata.clear()

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

    import app.routes.auth as auth_routes

    importlib.reload(auth_routes)

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


def test_admin_can_disable_user_and_user_cannot_login() -> None:
    prefix = "/s/e886e3c9ab5a7e147ea97/p/testproj"
    db_url = f"sqlite:///./test-{uuid.uuid4().hex}.db"
    app = _load_wrapped_app(db_url=db_url)

    import app.db as db
    from app.models import User

    _seed_user(
        db_engine=db.engine,
        email="admin@example.com",
        password="admin123",
        is_admin=True,
    )
    user_id = _seed_user(
        db_engine=db.engine,
        email="user@example.com",
        password="pw",
        is_admin=False,
    )

    admin_client = TestClient(app, base_url="http://testserver", root_path=prefix)

    r_login = admin_client.post(
        f"{prefix}/admin/login",
        data={"email": "admin@example.com", "password": "admin123"},
        follow_redirects=False,
    )
    assert r_login.status_code == 303

    r_edit = admin_client.get(f"{prefix}/admin/users/{user_id}")
    assert r_edit.status_code == 200
    assert "Edit user" in r_edit.text

    # Disable the user by omitting is_active.
    r_update = admin_client.post(
        f"{prefix}/admin/users/{user_id}/update",
        data={"is_admin": ""},
        follow_redirects=False,
    )
    assert r_update.status_code == 303

    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.id == user_id)).first()
        assert u
        assert u.is_active is False

    # The disabled user should not be able to log in (HTML form).
    client2 = TestClient(app, base_url="http://testserver", root_path=prefix)
    r_html_login = client2.post(
        f"{prefix}/login",
        data={"email": "user@example.com", "password": "pw"},
        follow_redirects=False,
    )
    assert r_html_login.status_code == 400
    assert "Invalid email or password" in r_html_login.text

    # The disabled user should not be able to get a token (API).
    r_api = client2.post(
        f"{prefix}/auth/token",
        data={"username": "user@example.com", "password": "pw"},
        follow_redirects=False,
    )
    assert r_api.status_code == 400


def test_admin_can_delete_user() -> None:
    prefix = "/s/e886e3c9ab5a7e147ea97/p/testproj"
    db_url = f"sqlite:///./test-{uuid.uuid4().hex}.db"
    app = _load_wrapped_app(db_url=db_url)

    import app.db as db
    from app.models import User

    _seed_user(
        db_engine=db.engine,
        email="admin@example.com",
        password="admin123",
        is_admin=True,
    )
    user_id = _seed_user(
        db_engine=db.engine,
        email="deleteme@example.com",
        password="pw",
        is_admin=False,
    )

    admin_client = TestClient(app, base_url="http://testserver", root_path=prefix)
    r_login = admin_client.post(
        f"{prefix}/admin/login",
        data={"email": "admin@example.com", "password": "admin123"},
        follow_redirects=False,
    )
    assert r_login.status_code == 303

    r_del = admin_client.post(
        f"{prefix}/admin/users/{user_id}/delete",
        data={"confirm": "1"},
        follow_redirects=False,
    )
    assert r_del.status_code == 303

    with Session(db.engine) as s:
        u = s.exec(select(User).where(User.id == user_id)).first()
        assert u is None
