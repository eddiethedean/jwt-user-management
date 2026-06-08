"""seed optional normal (non-admin) user

Revision ID: 0003_seed_user
Revises: 0002_seed_admin
Create Date: 2026-06-08

Idempotent user seed. Runs only when both ``SEED_USER_EMAIL`` and
``SEED_USER_PASSWORD`` are set in the environment at migrate time (e.g. from ``.env``).
Creates a non-admin account if that email is not already present.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0003_seed_user"
down_revision = "0002_seed_admin"
branch_labels = None
depends_on = None

_MIN_PASSWORD_LEN = 12
_WEAK_PASSWORDS = frozenset(
    {
        "admin123",
        "password",
        "changeme",
        "secret",
        "dev-secret",
        "passwordpassword",
    }
)


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _seed_credentials() -> tuple[str, str] | None:
    email = _env("SEED_USER_EMAIL")
    password = _env("SEED_USER_PASSWORD")
    if not email or not password:
        return None
    return email, password


def _validate_seed_password(password: str) -> None:
    if len(password) < _MIN_PASSWORD_LEN:
        raise RuntimeError(
            f"SEED_USER_PASSWORD must be at least {_MIN_PASSWORD_LEN} characters"
        )
    if password.lower() in _WEAK_PASSWORDS:
        raise RuntimeError("SEED_USER_PASSWORD is too weak; choose a stronger password")


def upgrade() -> None:
    creds = _seed_credentials()
    if not creds:
        return

    email, password = creds
    _validate_seed_password(password)

    from app.core.security import hash_password

    conn = op.get_bind()
    users = sa.table(
        "users",
        sa.column("id", sa.Integer()),
        sa.column("email", sa.String()),
        sa.column("hashed_password", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("is_admin", sa.Boolean()),
        sa.column("token_version", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    existing = conn.execute(
        sa.select(users.c.id).where(users.c.email == email).limit(1)
    ).fetchone()
    if not existing:
        conn.execute(
            users.insert().values(
                email=email,
                hashed_password=hash_password(password),
                is_active=True,
                is_admin=False,
                token_version=0,
                created_at=datetime.now(timezone.utc),
            )
        )


def downgrade() -> None:
    email = _env("SEED_USER_EMAIL")
    if not email:
        return
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM users WHERE email = :email AND is_admin = 0"),
        {"email": email},
    )
