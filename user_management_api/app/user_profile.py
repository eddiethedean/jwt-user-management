from __future__ import annotations

from typing import Any

import app.core.config as app_config
from app.models import User
from app.services.directory import DirectoryEmailRecord


def user_command_field_enabled() -> bool:
    return bool(app_config.settings.user_command_field_enabled)


def _strip_opt(value: str | None) -> str | None:
    if value is None:
        return None
    s = value.strip()
    return s or None


def user_to_api_dict(user: User) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "country": user.country,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
    }
    if user_command_field_enabled():
        out["command"] = getattr(user, "command", None)
    return out


def directory_record_to_lookup_dict(rec: DirectoryEmailRecord | None) -> dict[str, str]:
    if not rec:
        return {"email": "", "country": "", "display_name": "", "command": ""}
    out = {
        "email": rec.email,
        "country": rec.country or "",
        "display_name": rec.display_name or "",
        "command": rec.command or "",
    }
    if not user_command_field_enabled():
        out["command"] = ""
    return out


def apply_profile_fields_to_user(
    user: User,
    *,
    full_name: str | None = None,
    country: str | None = None,
    command: str | None = None,
    allow_overrides: bool = True,
) -> None:
    if allow_overrides and full_name is not None:
        fn = _strip_opt(full_name)
        if fn:
            user.full_name = fn
    if allow_overrides and country is not None:
        c = _strip_opt(country)
        if c:
            user.country = c
    if user_command_field_enabled() and allow_overrides and command is not None:
        cmd = _strip_opt(command)
        if cmd:
            user.command = cmd


def enrich_user_from_directory(
    user: User,
    rec: DirectoryEmailRecord | None,
    *,
    fill_missing_only: bool = True,
) -> None:
    if not rec:
        return
    if rec.display_name and (not fill_missing_only or not user.full_name):
        user.full_name = rec.display_name
    if rec.country and (not fill_missing_only or not user.country):
        user.country = rec.country
    if user_command_field_enabled() and rec.command:
        if not fill_missing_only or not getattr(user, "command", None):
            user.command = rec.command


def new_user_from_invite(
    *,
    email: str,
    password_hash: str,
    is_admin: bool,
    full_name: str | None = None,
    country: str | None = None,
    command: str | None = None,
    directory_rec: DirectoryEmailRecord | None = None,
) -> User:
    user = User(
        email=email,
        full_name=_strip_opt(full_name),
        country=_strip_opt(country),
        hashed_password=password_hash,
        is_admin=is_admin,
    )
    if user_command_field_enabled():
        user.command = _strip_opt(command)
    if directory_rec and app_config.settings.invite_accept_directory_enrich:
        enrich_user_from_directory(user, directory_rec, fill_missing_only=False)
    return user
