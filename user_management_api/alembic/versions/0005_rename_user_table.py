"""rename user table to users

Revision ID: 0005_rename_user_table
Revises: 0004_seed_admin_user
Create Date: 2026-04-28

"""

from alembic import op


revision = "0005_rename_user_table"
down_revision = "0004_seed_admin_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 'user' is a reserved keyword in some DBs (e.g., Postgres).
    # Rename to a safer plural table name.
    op.rename_table("user", "users")


def downgrade() -> None:
    op.rename_table("users", "user")
