"""make token_hash unique + add indexes

Revision ID: 0003_unique_token_hashes
Revises: 0002_password_reset_tokens
Create Date: 2026-04-21

"""

from alembic import op


revision = "0003_unique_token_hashes"
down_revision = "0002_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Invite tokens: token_hash should uniquely identify a single token.
    op.drop_index(op.f("ix_invitetoken_token_hash"), table_name="invitetoken")
    op.create_index(
        op.f("ix_invitetoken_token_hash"),
        "invitetoken",
        ["token_hash"],
        unique=True,
    )

    # Password reset tokens: same uniqueness guarantee + operational indexes.
    op.drop_index(
        op.f("ix_passwordresettoken_token_hash"), table_name="passwordresettoken"
    )
    op.create_index(
        op.f("ix_passwordresettoken_token_hash"),
        "passwordresettoken",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_passwordresettoken_expires_at"),
        "passwordresettoken",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_passwordresettoken_used_at"),
        "passwordresettoken",
        ["used_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_passwordresettoken_used_at"), table_name="passwordresettoken"
    )
    op.drop_index(
        op.f("ix_passwordresettoken_expires_at"), table_name="passwordresettoken"
    )
    op.drop_index(
        op.f("ix_passwordresettoken_token_hash"), table_name="passwordresettoken"
    )
    op.create_index(
        op.f("ix_passwordresettoken_token_hash"),
        "passwordresettoken",
        ["token_hash"],
        unique=False,
    )

    op.drop_index(op.f("ix_invitetoken_token_hash"), table_name="invitetoken")
    op.create_index(
        op.f("ix_invitetoken_token_hash"),
        "invitetoken",
        ["token_hash"],
        unique=False,
    )
