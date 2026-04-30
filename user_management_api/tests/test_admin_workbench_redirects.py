from __future__ import annotations

import importlib
import os
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel
from starlette.types import ASGIApp


def _load_wrapped_app(*, db_url: str) -> ASGIApp:
    """
    Reload backend modules that read settings at import time and return the ASGI app
    wrapped by the Workbench adapter (app.asgi:app).
    """
    os.environ["DATABASE_URL"] = db_url
    os.environ["JWT_SECRET"] = "test-secret"

    # Avoid SQLAlchemy table redefinition issues across reloads.
    SQLModel.metadata.clear()

    import app.core.config as config

    importlib.reload(config)

    import app.db as db

    importlib.reload(db)

    import app.core.security as security

    importlib.reload(security)

    import app.routes.admin as admin_routes

    importlib.reload(admin_routes)

    import app.main as main

    importlib.reload(main)

    import app.asgi as asgi

    importlib.reload(asgi)

    # Ensure schema exists.
    SQLModel.metadata.create_all(db.engine)
    return asgi.app  # type: ignore[return-value]


def _seed_admin(*, db_engine) -> None:
    from app.core.security import hash_password
    from app.models import User

    with Session(db_engine) as s:
        s.add(
            User(
                email="admin@example.com",
                hashed_password=hash_password("admin123"),
                created_at=datetime.now(timezone.utc),
            )
        )
        s.commit()


def test_admin_redirects_use_relative_locations_under_workbench_prefix() -> None:
    prefix = "/s/e886e3c9ab5a7e147ea97/p/testproj"
    db_url = f"sqlite:///./test-{uuid.uuid4().hex}.db"
    app = _load_wrapped_app(db_url=db_url)

    # Seed admin user for login test.
    import app.db as db

    _seed_admin(db_engine=db.engine)

    client = TestClient(app, base_url="http://testserver", root_path=prefix)

    r = client.get(f"{prefix}/admin", follow_redirects=False)
    assert r.status_code == 303
    # Relative redirect is required to avoid Workbench rewriting to /proxy/<port>/...
    assert r.headers["location"] == "admin/login"

    r2 = client.post(
        f"{prefix}/admin/login",
        data={"email": "admin@example.com", "password": "admin123"},
        follow_redirects=False,
    )
    assert r2.status_code == 303
    loc = r2.headers["location"]
    assert loc.startswith("../admin?token=")
    token = loc.split("token=", 1)[1]
    assert token

    # Admin page should accept invite creation via form POST and render invite URL.
    r3 = client.post(
        f"{prefix}/admin/invite",
        data={"token": token, "email": "new.user@example.com"},
        follow_redirects=False,
    )
    assert r3.status_code == 200
    assert "/invites/accept?token=" in r3.text
