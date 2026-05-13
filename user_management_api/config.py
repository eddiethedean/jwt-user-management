"""
Application defaults that are safe to commit (no secrets, no credentials).

``app.core.config.Settings`` loads ``.env`` from this package directory and merges
environment variables on top of these values. Constants defined here supply the
default for: URL/proxy paths, legacy cookie behaviour, generic SMTP transport flags
(port/TLS only), and directory client timeouts/flags (not the directory service URL).

Put in ``.env`` instead (see ``.env.example``): ``DATABASE_URL``, ``JWT_SECRET``,
``JWT_ALGORITHM``, ``JWT_EXPIRES_MINUTES``, ``DIRECTORY_LOOKUP_URL``,
``DIRECTORY_LOOKUP_CA_BUNDLE``, ``SMTP_HOST`` / username / password / from-address,
``SEED_*``, and any other secret or deployment-specific override.
"""

# --- URLs / proxy (env: BASE_PATH, PUBLIC_BASE_URL) ---
BASE_PATH: str = ""
PUBLIC_BASE_URL: str = "http://127.0.0.1:8001"

# --- Legacy HTML cookie helpers (env: COOKIE_DEBUG, AUTH_COOKIE_*) ---
COOKIE_DEBUG: bool = False
AUTH_COOKIE_SAMESITE: str = "lax"
AUTH_COOKIE_PARTITIONED: bool = False
AUTH_COOKIE_LEGACY: bool = True

# --- SMTP non-credentials (env: SMTP_PORT, SMTP_USE_TLS) ---
SMTP_PORT: int = 25
SMTP_USE_TLS: bool = False

# --- Directory lookup non-URL flags (env: DIRECTORY_LOOKUP_*) ---
DIRECTORY_LOOKUP_TIMEOUT_S: int = 5
DIRECTORY_LOOKUP_REQUIRED: bool = False
DIRECTORY_LOOKUP_VERIFY_SSL: bool = False
