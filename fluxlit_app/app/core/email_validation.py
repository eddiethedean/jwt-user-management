from __future__ import annotations

import re

_CONTROL_OR_WHITESPACE = re.compile(r"[\x00-\x1f\x7f]")


def normalize_email(value: str) -> str:
    """Strip and lower-case an email address."""
    return (value or "").strip().lower()


def validate_email_format(email: str) -> str:
    """
    Validate email format; reject CR/LF and control characters.

    Returns normalized email. Raises ValueError on invalid input.
    """
    e = normalize_email(email)
    if not e or "@" not in e:
        raise ValueError("Invalid email address")
    if _CONTROL_OR_WHITESPACE.search(e):
        raise ValueError("Invalid email address")
    local, _, domain = e.rpartition("@")
    if not local or not domain or "." not in domain:
        raise ValueError("Invalid email address")
    return e
