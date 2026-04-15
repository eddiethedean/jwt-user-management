"""initial tables

Revision ID: 0001_init
Revises:
Create Date: 2026-04-15

"""

from alembic import op
import sqlalchemy as sa


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("ad_object_id", sa.String(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_created_at"), "user", ["created_at"], unique=False)
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)

    op.create_table(
        "invitetoken",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("invited_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_invitetoken_created_at"), "invitetoken", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_invitetoken_email"), "invitetoken", ["email"], unique=False
    )
    op.create_index(
        op.f("ix_invitetoken_expires_at"), "invitetoken", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_invitetoken_invited_by_user_id"),
        "invitetoken",
        ["invited_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_invitetoken_token_hash"), "invitetoken", ["token_hash"], unique=False
    )
    op.create_index(
        op.f("ix_invitetoken_used_at"), "invitetoken", ["used_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_invitetoken_used_at"), table_name="invitetoken")
    op.drop_index(op.f("ix_invitetoken_token_hash"), table_name="invitetoken")
    op.drop_index(op.f("ix_invitetoken_invited_by_user_id"), table_name="invitetoken")
    op.drop_index(op.f("ix_invitetoken_expires_at"), table_name="invitetoken")
    op.drop_index(op.f("ix_invitetoken_email"), table_name="invitetoken")
    op.drop_index(op.f("ix_invitetoken_created_at"), table_name="invitetoken")
    op.drop_table("invitetoken")

    op.drop_index(op.f("ix_user_email"), table_name="user")
    op.drop_index(op.f("ix_user_created_at"), table_name="user")
    op.drop_table("user")
