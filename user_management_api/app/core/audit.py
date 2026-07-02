"""Structured audit logging for security-sensitive application events."""

from __future__ import annotations

from app.core.logging import get_logger

log = get_logger("audit")


def require_user_id(user_id: int | None) -> int:
    """Narrow optional DB primary keys for audit logs on persisted rows."""
    if user_id is None:
        raise RuntimeError("audit log requires persisted user id")
    return user_id


def log_auth_success(
    *, method: str, email: str, user_id: int, is_admin: bool = False
) -> None:
    log.info(
        "auth_success method=%s email=%s user_id=%s admin=%s",
        method,
        email,
        user_id,
        is_admin,
    )


def log_auth_failure(*, method: str, email: str, reason: str) -> None:
    log.warning(
        "auth_failed method=%s email=%s reason=%s",
        method,
        email or "",
        reason,
    )


def log_logout(*, method: str, email: str | None, user_id: int | None) -> None:
    log.info(
        "logout method=%s email=%s user_id=%s",
        method,
        email or "",
        user_id if user_id is not None else "",
    )


def log_registration(
    *,
    email: str,
    email_sent: bool,
    existing_user: bool = False,
    method: str = "register",
) -> None:
    if existing_user:
        log.info(
            "registration_existing_user method=%s email=%s",
            method,
            email,
        )
        return
    log.info(
        "registration_created method=%s email=%s email_sent=%s",
        method,
        email,
        email_sent,
    )


def log_registration_denied(
    *, email: str, reason: str, method: str = "register"
) -> None:
    log.warning(
        "registration_denied method=%s email=%s reason=%s",
        method,
        email or "",
        reason,
    )


def log_invite_created(
    *,
    email: str,
    grant_admin: bool,
    actor_email: str | None,
    method: str,
) -> None:
    log.info(
        "invite_created method=%s email=%s grant_admin=%s actor=%s",
        method,
        email,
        grant_admin,
        actor_email or "",
    )


def log_invite_accepted(*, email: str, user_id: int, grant_admin: bool) -> None:
    log.info(
        "invite_accepted email=%s user_id=%s grant_admin=%s",
        email,
        user_id,
        grant_admin,
    )


def log_invite_accept_failed(*, reason: str) -> None:
    log.warning("invite_accept_failed reason=%s", reason)


def log_password_reset_requested(*, email: str, user_found: bool) -> None:
    log.info(
        "password_reset_requested email=%s user_found=%s",
        email,
        user_found,
    )


def log_password_reset_completed(*, email: str, user_id: int) -> None:
    log.info("password_reset_completed email=%s user_id=%s", email, user_id)


def log_password_change(*, email: str, user_id: int, method: str) -> None:
    log.info(
        "password_changed method=%s email=%s user_id=%s",
        method,
        email,
        user_id,
    )


def log_profile_update(*, email: str, user_id: int, method: str) -> None:
    log.info(
        "profile_updated method=%s email=%s user_id=%s",
        method,
        email,
        user_id,
    )


def log_admin_user_updated(
    *,
    actor_email: str,
    actor_id: int,
    target_user_id: int,
    target_email: str,
    fields: str,
    method: str,
) -> None:
    log.info(
        "admin_user_updated method=%s actor=%s actor_id=%s target_id=%s "
        "target_email=%s fields=%s",
        method,
        actor_email,
        actor_id,
        target_user_id,
        target_email,
        fields,
    )


def log_admin_user_deleted(
    *,
    actor_email: str,
    actor_id: int,
    target_user_id: int,
    target_email: str,
    method: str,
) -> None:
    log.info(
        "admin_user_deleted method=%s actor=%s actor_id=%s target_id=%s target_email=%s",
        method,
        actor_email,
        actor_id,
        target_user_id,
        target_email,
    )


def log_admin_access_denied(
    *, email: str | None, user_id: int | None, path: str
) -> None:
    log.warning(
        "admin_access_denied email=%s user_id=%s path=%s",
        email or "",
        user_id if user_id is not None else "",
        path,
    )


def log_rate_limited(*, scope: str, ip: str, email: str | None = None) -> None:
    log.warning(
        "rate_limited scope=%s ip=%s email=%s",
        scope,
        ip,
        email or "",
    )


def log_token_rejected(*, reason: str, detail: str = "") -> None:
    log.warning("token_rejected reason=%s detail=%s", reason, detail or "")


def log_csrf_failed(*, path: str, method: str) -> None:
    log.warning("csrf_failed method=%s path=%s", method, path)


def log_email_sent(*, kind: str, to_email: str) -> None:
    log.info("email_sent kind=%s to=%s", kind, to_email)
