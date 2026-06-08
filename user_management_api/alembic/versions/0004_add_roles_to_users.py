"""add roles column to users

Revision ID: 0004_add_roles_to_users
Revises: 0003_seed_user
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_add_roles_to_users"
down_revision = "0003_seed_user"
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
