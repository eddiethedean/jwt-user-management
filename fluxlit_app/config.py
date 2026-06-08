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
# When False (default), do not fall back to port 25 without TLS on connection errors.
SMTP_ALLOW_LEGACY_PORT25_FALLBACK: bool = False

# --- Rate limiting (in-process; use proxy limits for multi-worker) ---
RATE_LIMIT_ENABLED: bool = True
RATE_LIMIT_AUTH_PER_MINUTE: int = 20
# Comma-separated proxy IPs that may set X-Forwarded-For (empty = never trust XFF).
RATE_LIMIT_TRUSTED_PROXIES: tuple[str, ...] = ()

# --- Self-registration ---
# When False, disable POST /register.
SELF_REGISTRATION_ENABLED: bool = True

# --- User roles (optional multi-assign on admin edit user page) ---
USER_ROLES: tuple[str, ...] = ("Admin", "User", "Super")
# Subset of USER_ROLES that grant admin UI/API access.
ADMIN_ROLES: tuple[str, ...] = ("Admin", "Super")

DIRECTORY_LOOKUP_TIMEOUT_S: int = 5
DIRECTORY_LOOKUP_REQUIRED: bool = False
DIRECTORY_LOOKUP_VERIFY_SSL: bool = True

INVITE_ALLOWED_EMAIL_DOMAINS: tuple[str, ...] = ("socom.mil", "soc.mil")

# --- HTML UI branding (Streamlit masthead) ---
APP_TITLE: str = "User Management"
BRAND_TAG: str = "Demo"
BRAND_TAG_TITLE: str = "Demo app"
BRAND_STACK: tuple[str, ...] = (
    "FastAPI",
    "SQLModel",
    "JWT",
    "Streamlit",
    "FluxLit",
)
