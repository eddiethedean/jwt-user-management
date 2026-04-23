"""seed default admin user (optional)

Revision ID: 0004_seed_admin_user
Revises: 0003_unique_token_hashes
Create Date: 2026-04-23

"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "0004_seed_admin_user"
down_revision = "0003_unique_token_hashes"
branch_labels = None
depends_on = None


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def upgrade() -> None:
    """
    Seed an initial admin user if configured via env vars.

    Env vars:
    - SEED_ADMIN_EMAIL
    - SEED_ADMIN_PASSWORD
    - SEED_ADMIN_FULL_NAME (optional)

    This is idempotent: if the email already exists, no row is inserted.
    """
    email = _env("SEED_ADMIN_EMAIL")
    password = _env("SEED_ADMIN_PASSWORD")
    full_name = _env("SEED_ADMIN_FULL_NAME") or None
    if not email or not password:
        return

    # Import here to avoid import-time side effects during Alembic env setup.
    from app.core.security import hash_password

    conn = op.get_bind()

    existing = conn.execute(
        sa.text("SELECT id FROM user WHERE email = :email LIMIT 1"),
        {"email": email},
    ).fetchone()
    if existing:
        return

    hashed = hash_password(password)
    now = datetime.now(timezone.utc)

    conn.execute(
        sa.text(
            """
            INSERT INTO user
              (email, full_name, is_active, is_admin, permissions, email_verified, ad_object_id, hashed_password, created_at)
            VALUES
              (:email, :full_name, :is_active, :is_admin, :permissions, :email_verified, :ad_object_id, :hashed_password, :created_at)
            """
        ),
        {
            "email": email,
            "full_name": full_name,
            "is_active": True,
            "is_admin": True,
            "permissions": "[]",
            "email_verified": True,
            "ad_object_id": None,
            "hashed_password": hashed,
            "created_at": now,
        },
    )


def downgrade() -> None:
    # We can't safely delete without knowing which row was seeded; leave as no-op.
    return
