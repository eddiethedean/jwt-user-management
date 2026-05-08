"""add full_name to users

Revision ID: 85a64e661d1a
Revises: 0001_initial_schema
Create Date: 2026-05-06 14:17:04.858545

"""

from alembic import op
import sqlalchemy as sa


revision = "85a64e661d1a"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "full_name")
