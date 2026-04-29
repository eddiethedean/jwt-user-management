"""seed admin user

Revision ID: 0002_seed_admin_user
Revises: 0001_create_users
Create Date: 2026-04-29

"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "0002_seed_admin_user"
down_revision = "0001_create_users"
branch_labels = None
depends_on = None


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def upgrade() -> None:
    """
    Seed an initial admin account (bare-bones).

    Env vars (optional):
    - SEED_ADMIN_EMAIL (default: admin@example.com)
    - SEED_ADMIN_PASSWORD (default: admin123)

    Idempotent: if the email already exists, does nothing.
    """
    email = _env("SEED_ADMIN_EMAIL") or "admin@example.com"
    password = _env("SEED_ADMIN_PASSWORD") or "admin123"

    # Import here to avoid import-time side effects during Alembic env setup.
    from app.core.security import hash_password

    conn = op.get_bind()

    users = sa.table(
        "users",
        sa.column("id", sa.Integer()),
        sa.column("email", sa.String()),
        sa.column("hashed_password", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    existing = conn.execute(
        sa.select(users.c.id).where(users.c.email == email).limit(1)
    ).fetchone()
    if existing:
        return

    conn.execute(
        users.insert().values(
            email=email,
            hashed_password=hash_password(password),
            created_at=datetime.now(timezone.utc),
        )
    )


def downgrade() -> None:
    # Don't delete rows on downgrade; leave as no-op.
    return

