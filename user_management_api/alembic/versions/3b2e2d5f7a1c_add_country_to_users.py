"""add country to users

Revision ID: 3b2e2d5f7a1c
Revises: 85a64e661d1a
Create Date: 2026-05-07

"""

from alembic import op
import sqlalchemy as sa


revision = "3b2e2d5f7a1c"
down_revision = "85a64e661d1a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("country", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "country")

