from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # dev|prod
    environment: str = "prod"

    # Optional flag (same name as Streamlit DEBUG=); ignored by API logic today.
    debug: bool = False

    database_url: str = "sqlite:///./app.db"
    public_base_url: str = "http://localhost:8000"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60

    admin_api_key: Optional[str] = None

    # Optional seed user (used by Alembic migration 0004_seed_admin_user).
    # These are intentionally optional and are treated as disabled when empty.
    seed_admin_email: Optional[str] = None
    seed_admin_password: Optional[str] = None
    seed_admin_full_name: Optional[str] = None

    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_use_tls: bool = True

    azure_tenant_id: Optional[str] = None
    azure_client_id: Optional[str] = None
    azure_client_secret: Optional[str] = None

    rate_limit_enabled: bool = True
    rate_limit_trust_proxy_headers: bool = False

    @field_validator("jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, v: str, info):
        v = (v or "").strip()
        if not v:
            raise ValueError("JWT_SECRET must be set")
        env = (info.data.get("environment") or "dev").lower()
        if env != "dev":
            if v.lower() == "change-me" or len(v) < 24:
                raise ValueError(
                    "JWT_SECRET must be a strong secret (>=24 chars) outside dev"
                )
        return v

    @field_validator("admin_api_key")
    @classmethod
    def _validate_admin_api_key(cls, v: Optional[str], info):
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        env = (info.data.get("environment") or "prod").lower()
        if env != "dev":
            if v.lower() in {"change-me", "change-me-too"} or len(v) < 24:
                raise ValueError(
                    "ADMIN_API_KEY must be a strong secret (>=24 chars) outside dev"
                )
        return v

    @field_validator("seed_admin_email", "seed_admin_password", "seed_admin_full_name")
    @classmethod
    def _normalize_seed_values(cls, v: Optional[str]):
        if v is None:
            return None
        v = v.strip()
        return v or None


settings = Settings()
