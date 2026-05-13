from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_cfg_path = Path(__file__).resolve().parents[2] / "config.py"
_spec = spec_from_file_location("fluxlit_app_pkg_config", _cfg_path)
assert _spec and _spec.loader
_defaults = module_from_spec(_spec)
_spec.loader.exec_module(_defaults)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "sqlite:///./app.db"
    base_path: str = Field(default=_defaults.BASE_PATH)
    public_base_url: str = Field(default=_defaults.PUBLIC_BASE_URL)
    jwt_secret: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60

    smtp_host: str = ""
    smtp_port: int = Field(default=_defaults.SMTP_PORT)
    smtp_use_tls: bool = Field(default=_defaults.SMTP_USE_TLS)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    directory_lookup_url: str = ""
    directory_lookup_timeout_s: int = Field(
        default=_defaults.DIRECTORY_LOOKUP_TIMEOUT_S
    )
    directory_lookup_required: bool = Field(
        default=_defaults.DIRECTORY_LOOKUP_REQUIRED
    )
    directory_lookup_verify_ssl: bool = Field(
        default=_defaults.DIRECTORY_LOOKUP_VERIFY_SSL
    )
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


settings = Settings()
