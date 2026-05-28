from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

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
        "cookie_debug",
        "auth_cookie_deployment",
        "auth_cookie_samesite",
        "auth_cookie_secure",
        "auth_cookie_domain",
        "auth_cookie_partitioned",
        "auth_cookie_legacy",
        "smtp_port",
        "smtp_use_tls",
        "directory_lookup_timeout_s",
        "directory_lookup_required",
        "directory_lookup_verify_ssl",
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
        self.ui_public_base_url = (
            str(getattr(d, "UI_PUBLIC_BASE_URL", "") or "")
        ).strip().rstrip("/")
        self.jwt_algorithm = (str(getattr(d, "JWT_ALGORITHM", "") or "HS256")).strip()
        self.jwt_expires_minutes = int(getattr(d, "JWT_EXPIRES_MINUTES", 60))

        self.cookie_debug = bool(getattr(d, "COOKIE_DEBUG", False))
        dep = (str(getattr(d, "AUTH_COOKIE_DEPLOYMENT", "local") or "local")).strip().lower()
        if dep not in {"local", "connect"}:
            raise ValueError("AUTH_COOKIE_DEPLOYMENT must be 'local' or 'connect'")
        self.auth_cookie_deployment = dep
        ss = (str(getattr(d, "AUTH_COOKIE_SAMESITE", "lax") or "lax")).strip().lower()
        if ss not in {"lax", "strict", "none"}:
            raise ValueError("AUTH_COOKIE_SAMESITE must be one of: lax, strict, none")
        self.auth_cookie_samesite = ss
        sec = getattr(d, "AUTH_COOKIE_SECURE", None)
        self.auth_cookie_secure = sec if isinstance(sec, (bool, type(None))) else None
        self.auth_cookie_domain = (str(getattr(d, "AUTH_COOKIE_DOMAIN", "") or "")).strip()
        self.auth_cookie_partitioned = bool(getattr(d, "AUTH_COOKIE_PARTITIONED", False))
        self.auth_cookie_legacy = bool(getattr(d, "AUTH_COOKIE_LEGACY", True))

        self.smtp_port = int(getattr(d, "SMTP_PORT", 25))
        self.smtp_use_tls = bool(getattr(d, "SMTP_USE_TLS", False))

        self.directory_lookup_timeout_s = int(getattr(d, "DIRECTORY_LOOKUP_TIMEOUT_S", 5))
        self.directory_lookup_required = bool(
            getattr(d, "DIRECTORY_LOOKUP_REQUIRED", False)
        )
        self.directory_lookup_verify_ssl = bool(
            getattr(d, "DIRECTORY_LOOKUP_VERIFY_SSL", False)
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
