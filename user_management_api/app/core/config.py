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
    jwt_secret: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60

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


settings = Settings()
