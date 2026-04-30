"""create invite tokens

Revision ID: 0003_create_invites
Revises: 0002_seed_admin_user
Create Date: 2026-04-30

"""

from alembic import op
import sqlalchemy as sa


revision = "0003_create_invites"
down_revision = "0002_seed_admin_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invite_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_invite_tokens_email"), "invite_tokens", ["email"], unique=False
    )
    op.create_index(
        op.f("ix_invite_tokens_token_hash"),
        "invite_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_invite_tokens_token_hash"), table_name="invite_tokens")
    op.drop_index(op.f("ix_invite_tokens_email"), table_name="invite_tokens")
    op.drop_table("invite_tokens")
