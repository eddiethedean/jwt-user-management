"""add command to users

Revision ID: c4e8f1a2b3d0
Revises: 3b2e2d5f7a1c
Create Date: 2026-05-28

"""

from alembic import op
import sqlalchemy as sa


revision = "c4e8f1a2b3d0"
down_revision = "3b2e2d5f7a1c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("command", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "command")
