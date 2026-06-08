from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_cfg_path = Path(__file__).resolve().parents[2] / "config.py"
_spec = spec_from_file_location("fluxlit_app_pkg_config", _cfg_path)
assert _spec and _spec.loader
_defaults = module_from_spec(_spec)
_spec.loader.exec_module(_defaults)


def _normalize_base_path(v: str) -> str:
    v = (v or "").strip()
    if not v:
        return ""
    if not v.startswith("/"):
        v = "/" + v
    if len(v) > 1 and v.endswith("/"):
        v = v[:-1]
    return v


class Secrets(BaseSettings):
    """Values read from ``.env`` only (secrets and deployment endpoints)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./app.db"
    jwt_secret: str = "dev-secret"

    smtp_host: str = ""
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    directory_lookup_url: str = ""
    directory_lookup_ca_bundle: str = ""

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_non_empty(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("JWT_SECRET must be set")
        weak = {"dev-secret", "secret", "changeme", "password", "jwt-secret"}
        if v.lower() in weak and not (
            os.getenv("JWT_ALLOW_WEAK_SECRET", "").strip().lower()
            in {"1", "true", "yes", "on"}
        ):
            raise ValueError(
                "JWT_SECRET is too weak; set a strong secret or JWT_ALLOW_WEAK_SECRET=1 for local dev"
            )
        if len(v) < 16 and not (
            os.getenv("JWT_ALLOW_WEAK_SECRET", "").strip().lower()
            in {"1", "true", "yes", "on"}
        ):
            raise ValueError(
                "JWT_SECRET must be at least 16 characters, or set JWT_ALLOW_WEAK_SECRET=1 for local dev"
            )
        return v


class Settings:
    """Secrets from ``.env`` plus tunables from ``config.py`` (no key overlap)."""

    __slots__ = (
        "database_url",
        "jwt_secret",
        "smtp_host",
        "smtp_username",
        "smtp_password",
        "smtp_from_email",
        "directory_lookup_url",
        "directory_lookup_ca_bundle",
        "base_path",
        "public_base_url",
        "jwt_algorithm",
        "jwt_expires_minutes",
        "smtp_port",
        "smtp_use_tls",
        "smtp_allow_legacy_port25_fallback",
        "rate_limit_enabled",
        "rate_limit_auth_per_minute",
        "rate_limit_trusted_proxies",
        "directory_lookup_timeout_s",
        "directory_lookup_required",
        "directory_lookup_verify_ssl",
        "user_roles",
        "admin_roles",
        "self_registration_enabled",
        "app_title",
        "brand_tag",
        "brand_tag_title",
        "brand_stack",
    )

    def __init__(self) -> None:
        s = Secrets()
        self.database_url = s.database_url
        self.jwt_secret = s.jwt_secret
        self.smtp_host = s.smtp_host
        self.smtp_username = s.smtp_username
        self.smtp_password = s.smtp_password
        self.smtp_from_email = s.smtp_from_email
        self.directory_lookup_url = s.directory_lookup_url
        self.directory_lookup_ca_bundle = s.directory_lookup_ca_bundle

        d = _defaults
        self.base_path = _normalize_base_path(str(getattr(d, "BASE_PATH", "") or ""))
        self.public_base_url = (str(getattr(d, "PUBLIC_BASE_URL", "") or "")).strip().rstrip(
            "/"
        )
        self.jwt_algorithm = (str(getattr(d, "JWT_ALGORITHM", "") or "HS256")).strip()
        self.jwt_expires_minutes = int(getattr(d, "JWT_EXPIRES_MINUTES", 60))

        self.smtp_port = int(getattr(d, "SMTP_PORT", 25))
        self.smtp_use_tls = bool(getattr(d, "SMTP_USE_TLS", False))
        self.smtp_allow_legacy_port25_fallback = bool(
            getattr(d, "SMTP_ALLOW_LEGACY_PORT25_FALLBACK", False)
        )

        self.rate_limit_enabled = bool(getattr(d, "RATE_LIMIT_ENABLED", True))
        self.rate_limit_auth_per_minute = int(
            getattr(d, "RATE_LIMIT_AUTH_PER_MINUTE", 20)
        )
        self.rate_limit_trusted_proxies = frozenset(
            str(x).strip()
            for x in getattr(d, "RATE_LIMIT_TRUSTED_PROXIES", ()) or ()
            if str(x).strip()
        )

        self.directory_lookup_timeout_s = int(getattr(d, "DIRECTORY_LOOKUP_TIMEOUT_S", 5))
        self.directory_lookup_required = bool(
            getattr(d, "DIRECTORY_LOOKUP_REQUIRED", False)
        )
        self.directory_lookup_verify_ssl = bool(
            getattr(d, "DIRECTORY_LOOKUP_VERIFY_SSL", True)
        )

        self.user_roles = tuple(
            str(x).strip() for x in getattr(d, "USER_ROLES", ()) or () if str(x).strip()
        )
        admin_roles = tuple(
            str(x).strip()
            for x in getattr(d, "ADMIN_ROLES", ()) or ()
            if str(x).strip()
        )
        unknown_admin = [r for r in admin_roles if r not in self.user_roles]
        if unknown_admin:
            raise ValueError(
                "ADMIN_ROLES must be a subset of USER_ROLES; "
                f"unknown: {', '.join(unknown_admin)}"
            )
        self.admin_roles = admin_roles

        self.self_registration_enabled = bool(
            getattr(d, "SELF_REGISTRATION_ENABLED", True)
        )

        self.app_title = (
            str(getattr(d, "APP_TITLE", "") or "User Management").strip()
            or "User Management"
        )
        self.brand_tag = str(getattr(d, "BRAND_TAG", "") or "").strip()
        self.brand_tag_title = str(getattr(d, "BRAND_TAG_TITLE", "") or "").strip()
        self.brand_stack = tuple(
            str(x).strip()
            for x in getattr(d, "BRAND_STACK", ()) or ()
            if str(x).strip()
        )

    def normalized_invite_email_domains(self) -> frozenset[str]:
        return frozenset(
            str(x).strip().lower().lstrip("@")
            for x in _defaults.INVITE_ALLOWED_EMAIL_DOMAINS
            if str(x).strip()
        )


settings = Settings()


def refresh_settings() -> None:
    """Rebuild ``settings`` after mutating ``_defaults`` (e.g. in tests)."""
    global settings
    settings = Settings()
