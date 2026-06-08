"""Invite / self-registration email domain allowlist (see ``config.py`` defaults)."""

from __future__ import annotations


def invite_email_domain_allowed(email: str) -> bool:
    """Return True if ``email`` domain is in the configured allowlist."""
    from app.core.config import settings

    allowed = settings.normalized_invite_email_domains()
    if not allowed:
        return False
    e = (email or "").strip().lower()
    if "@" not in e:
        return False
    domain = e.rsplit("@", 1)[-1]
    return domain in allowed
