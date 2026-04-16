from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # dev|prod (demo defaults to dev)
    environment: str = "dev"

    database_url: str = "sqlite:///./app.db"
    public_base_url: str = "http://localhost:8000"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60

    admin_api_key: Optional[str] = None

    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_use_tls: bool = True

    azure_tenant_id: Optional[str] = None
    azure_client_id: Optional[str] = None
    azure_client_secret: Optional[str] = None

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


settings = Settings()
