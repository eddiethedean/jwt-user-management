"""
Committed application defaults (no secrets, no credentials).

Edit this file to change behavior for every environment. Do **not** duplicate these
keys in ``.env`` — tunables live here only.

Secrets and deployment endpoints belong in ``.env`` only — see ``.env.example``.
"""

BASE_PATH: str = ""
PUBLIC_BASE_URL: str = "http://127.0.0.1:8000"

JWT_ALGORITHM: str = "HS256"
JWT_EXPIRES_MINUTES: int = 60

SMTP_PORT: int = 25
SMTP_USE_TLS: bool = False

DIRECTORY_LOOKUP_TIMEOUT_S: int = 5
DIRECTORY_LOOKUP_REQUIRED: bool = False
DIRECTORY_LOOKUP_VERIFY_SSL: bool = False

INVITE_ALLOWED_EMAIL_DOMAINS: tuple[str, ...] = ("socom.mil", "soc.mil")
