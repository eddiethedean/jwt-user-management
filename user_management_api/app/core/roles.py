"""Configurable user roles (stored on ``User.roles`` as comma-separated labels)."""

from __future__ import annotations

from typing import Iterable

from app.models import User


def parse_user_roles(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(
        part.strip()
        for part in str(raw).split(",")
        if part.strip()
    )


def serialize_user_roles(roles: Iterable[str]) -> str | None:
    labels = sorted({str(r).strip() for r in roles if str(r).strip()})
    return ",".join(labels) if labels else None


def normalize_selected_roles(
    selected: Iterable[str], allowed_roles: tuple[str, ...]
) -> frozenset[str]:
    allowed = frozenset(allowed_roles)
    return frozenset(r for r in selected if r in allowed)


def effective_user_roles(
    user: User, allowed_roles: tuple[str, ...]
) -> frozenset[str]:
    stored = parse_user_roles(getattr(user, "roles", None))
    if stored:
        return stored
    legacy: set[str] = set()
    if getattr(user, "is_admin", False) and "Admin" in allowed_roles:
        legacy.add("Admin")
    elif "User" in allowed_roles:
        legacy.add("User")
    return frozenset(legacy)


def display_user_roles(user: User, allowed_roles: tuple[str, ...]) -> list[str]:
    effective = effective_user_roles(user, allowed_roles)
    return [role for role in allowed_roles if role in effective]


def grants_admin(roles: frozenset[str], admin_roles: tuple[str, ...]) -> bool:
    return bool(roles & frozenset(admin_roles))


def apply_user_roles(
    user: User,
    selected: Iterable[str],
    *,
    allowed_roles: tuple[str, ...],
    admin_roles: tuple[str, ...],
) -> None:
    normalized = normalize_selected_roles(selected, allowed_roles)
    user.roles = serialize_user_roles(normalized)
    user.is_admin = grants_admin(normalized, admin_roles)
