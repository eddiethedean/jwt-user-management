from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "sqlite:///./app.db"
    # Optional external path prefix when behind a reverse proxy (e.g. Workbench):
    # Example: /s/<service>/p/<project>
    base_path: str = ""
    # External base URL used to generate invite links (scheme + host).
    # Example: https://workbench.socom.mil
    public_base_url: str = "http://127.0.0.1:8001"
    jwt_secret: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60

    # Cookie settings for HTML login session.
    # Note: When the app is embedded (e.g. in Connect UI iframe), you may need:
    # AUTH_COOKIE_SAMESITE=none and AUTH_COOKIE_SECURE=true
    cookie_debug: bool = False
    auth_cookie_samesite: str = "lax"  # lax|strict|none
    auth_cookie_secure: bool | None = (
        None  # None => infer from request scheme/forwarded proto
    )
    auth_cookie_domain: str = ""  # optional; usually leave blank
    # Some browsers require Partitioned cookies (CHIPS) for embedded apps.
    auth_cookie_partitioned: bool = False
    # Connect sets a secondary "-legacy" cookie without SameSite for compatibility.
    auth_cookie_legacy: bool = True

    # SMTP (optional). If SMTP_HOST and SMTP_FROM_EMAIL are unset, email sending is disabled.
    smtp_host: str = ""
    smtp_port: int = 25
    smtp_use_tls: bool = False
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    # Optional: directory lookup for validating emails in secure environments.
    # Example:
    # DIRECTORY_LOOKUP_URL=https://connect.socom.mil/api/ldapEmail
    directory_lookup_url: str = ""
    directory_lookup_timeout_s: int = 5
    directory_lookup_required: bool = False
    directory_lookup_verify_ssl: bool = False
    directory_lookup_ca_bundle: str = ""

    @field_validator("base_path")
    @classmethod
    def _validate_base_path(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            return ""
        if not v.startswith("/"):
            v = "/" + v
        if len(v) > 1 and v.endswith("/"):
            v = v[:-1]
        return v

    @field_validator("jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, v: str):
        v = (v or "").strip()
        if not v:
            raise ValueError("JWT_SECRET must be set")
        return v

    @field_validator("auth_cookie_samesite")
    @classmethod
    def _validate_cookie_samesite(cls, v: str) -> str:
        vv = (v or "").strip().lower()
        if vv not in {"lax", "strict", "none"}:
            raise ValueError("AUTH_COOKIE_SAMESITE must be one of: lax, strict, none")
        return vv

    @field_validator("auth_cookie_domain")
    @classmethod
    def _validate_cookie_domain(cls, v: str) -> str:
        return (v or "").strip()


settings = Settings()
