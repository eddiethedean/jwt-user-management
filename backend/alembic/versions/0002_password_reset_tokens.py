"""add password reset tokens

Revision ID: 0002_password_reset_tokens
Revises: 0001_init
Create Date: 2026-04-15

"""

from alembic import op
import sqlalchemy as sa


revision = "0002_password_reset_tokens"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "passwordresettoken",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_passwordresettoken_email"),
        "passwordresettoken",
        ["email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_passwordresettoken_token_hash"),
        "passwordresettoken",
        ["token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_passwordresettoken_token_hash"), table_name="passwordresettoken"
    )
    op.drop_index(op.f("ix_passwordresettoken_email"), table_name="passwordresettoken")
    op.drop_table("passwordresettoken")
