from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_cfg_path = Path(__file__).resolve().parents[2] / "config.py"
_spec = spec_from_file_location("user_management_api_pkg_config", _cfg_path)
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


def _normalize_suffixes(items: tuple[str, ...] | list[str]) -> frozenset[str]:
    return frozenset(
        str(x).strip().lower().lstrip("@") for x in items if str(x).strip()
    )


def _normalize_string_list(items: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(str(x).strip() for x in items if str(x).strip())


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
        if v.lower() in weak and os.getenv(
            "JWT_ALLOW_WEAK_SECRET", ""
        ).strip().lower() not in {"1", "true", "yes", "on"}:
            raise ValueError(
                "JWT_SECRET is too weak; set a strong secret or JWT_ALLOW_WEAK_SECRET=1 for local dev"
            )
        if len(v) < 16 and os.getenv(
            "JWT_ALLOW_WEAK_SECRET", ""
        ).strip().lower() not in {"1", "true", "yes", "on"}:
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
        "ui_public_base_url",
        "jwt_algorithm",
        "jwt_expires_minutes",
        "min_password_length",
        "user_command_field_enabled",
        "directory_attribute_profile",
        "registration_directory_lookup_enabled",
        "registration_directory_lookup_required",
        "invite_accept_allow_profile_overrides",
        "invite_accept_directory_enrich",
        "postgres_async_enabled",
        "postgres_ssl_relaxed",
        "ui_brand_title",
        "ui_brand_tag",
        "ui_brand_tag_tooltip",
        "ui_brand_subtitle",
        "ui_brand_stack_pills",
        "cookie_debug",
        "auth_cookie_deployment",
        "auth_cookie_samesite",
        "auth_cookie_secure",
        "auth_cookie_domain",
        "auth_cookie_partitioned",
        "auth_cookie_legacy",
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
        self.public_base_url = (
            (str(getattr(d, "PUBLIC_BASE_URL", "") or "")).strip().rstrip("/")
        )
        self.ui_public_base_url = (
            (str(getattr(d, "UI_PUBLIC_BASE_URL", "") or "")).strip().rstrip("/")
        )
        self.jwt_algorithm = (str(getattr(d, "JWT_ALGORITHM", "") or "HS256")).strip()
        self.jwt_expires_minutes = int(getattr(d, "JWT_EXPIRES_MINUTES", 60))

        mpl = int(getattr(d, "MIN_PASSWORD_LENGTH", 3))
        if mpl < 1:
            raise ValueError("MIN_PASSWORD_LENGTH must be at least 1")
        self.min_password_length = mpl

        self.user_command_field_enabled = bool(
            getattr(d, "USER_COMMAND_FIELD_ENABLED", False)
        )

        prof = (
            (str(getattr(d, "DIRECTORY_ATTRIBUTE_PROFILE", "generic") or "generic"))
            .strip()
            .lower()
        )
        if prof not in {"generic", "extended", "both"}:
            raise ValueError(
                "DIRECTORY_ATTRIBUTE_PROFILE must be 'generic', 'extended', or 'both'"
            )
        self.directory_attribute_profile = prof

        self.registration_directory_lookup_enabled = bool(
            getattr(d, "REGISTRATION_DIRECTORY_LOOKUP_ENABLED", False)
        )
        self.registration_directory_lookup_required = bool(
            getattr(d, "REGISTRATION_DIRECTORY_LOOKUP_REQUIRED", False)
        )

        self.invite_accept_allow_profile_overrides = bool(
            getattr(d, "INVITE_ACCEPT_ALLOW_PROFILE_OVERRIDES", True)
        )
        self.invite_accept_directory_enrich = bool(
            getattr(d, "INVITE_ACCEPT_DIRECTORY_ENRICH", True)
        )

        self.postgres_async_enabled = bool(getattr(d, "POSTGRES_ASYNC_ENABLED", True))
        self.postgres_ssl_relaxed = bool(getattr(d, "POSTGRES_SSL_RELAXED", True))

        self.ui_brand_title = (
            str(getattr(d, "UI_BRAND_TITLE", "User Management") or "User Management")
        ).strip() or "User Management"
        self.ui_brand_tag = str(getattr(d, "UI_BRAND_TAG", "") or "").strip()
        self.ui_brand_tag_tooltip = str(
            getattr(d, "UI_BRAND_TAG_TOOLTIP", "") or ""
        ).strip()
        self.ui_brand_subtitle = str(getattr(d, "UI_BRAND_SUBTITLE", "") or "").strip()
        self.ui_brand_stack_pills = _normalize_string_list(
            getattr(
                d,
                "UI_BRAND_STACK_PILLS",
                ("FastAPI", "SQLModel", "JWT"),
            )
        )

        self.cookie_debug = bool(getattr(d, "COOKIE_DEBUG", False))
        dep = (
            (str(getattr(d, "AUTH_COOKIE_DEPLOYMENT", "local") or "local"))
            .strip()
            .lower()
        )
        if dep not in {"local", "connect"}:
            raise ValueError("AUTH_COOKIE_DEPLOYMENT must be 'local' or 'connect'")
        self.auth_cookie_deployment = dep
        ss = (str(getattr(d, "AUTH_COOKIE_SAMESITE", "lax") or "lax")).strip().lower()
        if ss not in {"lax", "strict", "none"}:
            raise ValueError("AUTH_COOKIE_SAMESITE must be one of: lax, strict, none")
        self.auth_cookie_samesite = ss
        sec = getattr(d, "AUTH_COOKIE_SECURE", None)
        self.auth_cookie_secure = sec if isinstance(sec, (bool, type(None))) else None
        self.auth_cookie_domain = (
            str(getattr(d, "AUTH_COOKIE_DOMAIN", "") or "")
        ).strip()
        self.auth_cookie_partitioned = bool(
            getattr(d, "AUTH_COOKIE_PARTITIONED", False)
        )
        self.auth_cookie_legacy = bool(getattr(d, "AUTH_COOKIE_LEGACY", True))

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

        self.directory_lookup_timeout_s = int(
            getattr(d, "DIRECTORY_LOOKUP_TIMEOUT_S", 5)
        )
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

    def normalized_invite_email_domains(self) -> frozenset[str]:
        return _normalize_suffixes(_defaults.INVITE_ALLOWED_EMAIL_DOMAINS)

    def normalized_registration_directory_suffixes(self) -> frozenset[str]:
        return _normalize_suffixes(
            getattr(_defaults, "REGISTRATION_DIRECTORY_LOOKUP_SUFFIXES", ())
        )

    def registration_directory_applies_to_email(self, email: str) -> bool:
        if not self.registration_directory_lookup_enabled:
            return False
        if not (self.directory_lookup_url or "").strip():
            return False
        suffixes = self.normalized_registration_directory_suffixes()
        if not suffixes:
            return True
        email_l = (email or "").strip().lower()
        return any(email_l.endswith("@" + s) for s in suffixes)


settings = Settings()


def refresh_settings() -> None:
    """Rebuild ``settings`` after mutating ``_defaults`` (e.g. in tests)."""
    global settings
    settings = Settings()
