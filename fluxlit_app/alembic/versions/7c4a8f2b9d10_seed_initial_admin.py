"""seed initial admin

Revision ID: 7c4a8f2b9d10
Revises: 3b2e2d5f7a1c
Create Date: 2026-05-12

"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "7c4a8f2b9d10"
down_revision = "3b2e2d5f7a1c"
branch_labels = None
depends_on = None


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def upgrade() -> None:
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
                created_at=datetime.now(timezone.utc),
            )
        )


def downgrade() -> None:
    # Do not delete a real admin account during downgrade.
    pass
