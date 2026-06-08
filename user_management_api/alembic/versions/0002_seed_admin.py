"""seed initial admin account

Revision ID: 0002_seed_admin
Revises: 0001_initial_schema
Create Date: 2026-06-08

Idempotent admin seed. Skipped when ``SEED_ADMIN_ENABLED`` is set to a falsey
value (``0``, ``false``, ``no``, ``off``) in the environment at migrate time.
Otherwise creates the default admin if missing.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0002_seed_admin"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _seed_enabled() -> bool:
    flag = _env("SEED_ADMIN_ENABLED").lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    return True


def upgrade() -> None:
    if not _seed_enabled():
        return

    email = _env("SEED_ADMIN_EMAIL") or "admin@example.com"
    password = _env("SEED_ADMIN_PASSWORD") or "admin123"

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
                is_admin=True,
                token_version=0,
                created_at=datetime.now(timezone.utc),
            )
        )


def downgrade() -> None:
    email = _env("SEED_ADMIN_EMAIL") or "admin@example.com"
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM users WHERE email = :email"), {"email": email})
