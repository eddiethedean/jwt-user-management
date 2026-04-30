"""squashed admin flag migration (no-op)

Revision ID: 0004_admin_flag
Revises: 0003_create_invites
Create Date: 2026-04-30

This revision used to add `users.is_admin` and `invite_tokens.grant_admin`.
Those columns are now part of the initial schema, but we keep this revision as
a no-op so existing databases that were already migrated to 0004 continue to
work with `alembic upgrade head`.
"""

from __future__ import annotations


revision = "0004_admin_flag"
down_revision = "0003_create_invites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    return


def downgrade() -> None:
    return
