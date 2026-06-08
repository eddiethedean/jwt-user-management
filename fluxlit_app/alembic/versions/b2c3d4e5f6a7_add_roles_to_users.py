"""add roles column to users

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("roles", sa.String(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE users SET roles = 'Admin' "
            "WHERE is_admin = 1 AND (roles IS NULL OR roles = '')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE users SET roles = 'User' "
            "WHERE is_admin = 0 AND (roles IS NULL OR roles = '')"
        )
    )


def downgrade() -> None:
    op.drop_column("users", "roles")
