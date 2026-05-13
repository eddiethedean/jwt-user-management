"""
Committed application defaults (no secrets, no credentials).

Edit this file to change behavior for every environment. Do **not** duplicate these
keys in ``.env`` — tunables live here only.

Secrets and deployment endpoints (database URL, JWT secret, SMTP credentials, LDAP
base URL, CA bundle) belong in ``.env`` only — see ``.env.example``.
"""

# --- URLs / proxy ---
BASE_PATH: str = ""
PUBLIC_BASE_URL: str = "http://127.0.0.1:8001"

# Streamlit UI base for Option A emailed deep links. When non-empty, invite/reset
# emails use ``/?page=...&token=...`` for that host.
UI_PUBLIC_BASE_URL: str = ""

# --- JWT (non-secret algorithm / lifetime) ---
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRES_MINUTES: int = 60

# --- Legacy HTML cookie helpers ---
COOKIE_DEBUG: bool = False
AUTH_COOKIE_SAMESITE: str = "lax"
# None => infer secure flag from request scheme in cookie middleware.
AUTH_COOKIE_SECURE: bool | None = None
AUTH_COOKIE_DOMAIN: str = ""
AUTH_COOKIE_PARTITIONED: bool = False
AUTH_COOKIE_LEGACY: bool = True

# --- SMTP non-credentials (host / user / password / from → ``.env`` only) ---
SMTP_PORT: int = 25
SMTP_USE_TLS: bool = False

# --- Directory client (service URL → ``.env`` only) ---
DIRECTORY_LOOKUP_TIMEOUT_S: int = 5
DIRECTORY_LOOKUP_REQUIRED: bool = False
DIRECTORY_LOOKUP_VERIFY_SSL: bool = False

# --- Invite / self-registration email domains (suffix after ``@``) ---
INVITE_ALLOWED_EMAIL_DOMAINS: tuple[str, ...] = ("socom.mil", "soc.mil")
