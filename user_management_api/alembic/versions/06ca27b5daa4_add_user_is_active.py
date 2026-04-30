"""add user is_active

Revision ID: 06ca27b5daa4
Revises: c48583c52125
Create Date: 2026-04-30 15:51:21.032911

"""

from alembic import op
import sqlalchemy as sa


revision = "06ca27b5daa4"
down_revision = "c48583c52125"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.create_index(op.f("ix_users_is_active"), "users", ["is_active"])
    op.alter_column("users", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_is_active"), table_name="users")
    op.drop_column("users", "is_active")
