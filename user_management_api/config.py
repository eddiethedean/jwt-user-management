"""
Committed application defaults (no secrets, no credentials).

Edit this file to change behavior for every environment. Do **not** duplicate these
keys in ``.env`` — tunables live here only.

Secrets and deployment endpoints (database URL, JWT secret, SMTP credentials, LDAP
base URL, CA bundle) belong in ``.env`` only — see ``.env.example``.

Optional features (directory mapping, command field, registration LDAP gate,
Postgres async) are **off by default** unless enabled below.
"""

# --- Logging ---
# ``LOG_LEVEL`` may also be set in the process environment (e.g. by ``run_workbench.py``).
LOG_LEVEL: str = "info"
LOG_HTTP_REQUESTS: bool = True

# --- URLs / proxy ---
BASE_PATH: str = ""
PUBLIC_BASE_URL: str = "http://127.0.0.1:8001"

# --- JWT (non-secret algorithm / lifetime) ---
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRES_MINUTES: int = 60

# --- Password policy ---
MIN_PASSWORD_LENGTH: int = 3

# --- User profile fields ---
# When True, ``users.command`` is exposed in API responses and invite/admin updates.
USER_COMMAND_FIELD_ENABLED: bool = False

# --- Directory LDAP attribute mapping ---
#   "generic"  — displayName/cn; country from c/co (C=US normalized)
#   "extended" — givenName+sn; country from extensionAttribute8; command from department
#   "both"     — prefer extended attributes, fall back to generic
DIRECTORY_ATTRIBUTE_PROFILE: str = "generic"

# --- Self-registration directory gate ---
REGISTRATION_DIRECTORY_LOOKUP_ENABLED: bool = False
REGISTRATION_DIRECTORY_LOOKUP_REQUIRED: bool = False
# When non-empty, lookup runs only for these suffixes (after ``@``). Empty + enabled
# means lookup for every allowed registration domain.
REGISTRATION_DIRECTORY_LOOKUP_SUFFIXES: tuple[str, ...] = ()

# --- Invite accept (optional profile fields on accept) ---
INVITE_ACCEPT_ALLOW_PROFILE_OVERRIDES: bool = True
INVITE_ACCEPT_DIRECTORY_ENRICH: bool = True

# --- PostgreSQL async engine ---
# When DATABASE_URL is postgresql/postgres, use asyncpg for the app engine.
POSTGRES_ASYNC_ENABLED: bool = True
# Strip ``sslmode=require`` from the async URL and use a relaxed SSL context.
POSTGRES_SSL_RELAXED: bool = True

# When True, registration/forgot-password responses may include raw setup/reset URLs
# (intended for local dev without SMTP). Keep False in production.
EXPOSE_SETUP_URLS_IN_RESPONSE: bool = False

# --- Built-in HTML UI branding (``app/web/templates/base.html`` top bar) ---
UI_BRAND_TITLE: str = "User Management"
# Shown next to the title; leave empty to hide the tag pill.
UI_BRAND_TAG: str = "Demo"
UI_BRAND_TAG_TOOLTIP: str = "Demo app"
UI_BRAND_SUBTITLE: str = (
    "A minimal, browser-friendly user system with login, invites, and admin tools."
)
# Technology / stack labels under the subtitle (each entry is one pill).
UI_BRAND_STACK_PILLS: tuple[str, ...] = (
    "FastAPI",
    "SQLModel",
    "JWT",
    "HTML",
    "CSS",
    "JS",
)

# --- HTML UI cookie helpers ---
COOKIE_DEBUG: bool = False
# Auth cookie path/secure behavior for the built-in HTML UI and debug cookies.
#   "local"   — secure from request HTTPS (or AUTH_COOKIE_SECURE); path from Workbench base_path.
#   "connect" — secure=True and path="/" (Posit Connect embedded HTML; fixes dropped cookies).
AUTH_COOKIE_DEPLOYMENT: str = "local"
AUTH_COOKIE_SAMESITE: str = "lax"
# None => infer secure flag from request scheme (local mode only).
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
INVITE_ALLOWED_EMAIL_DOMAINS: tuple[str, ...] = ("example.com", "example.org")

# --- User roles (optional multi-assign on admin edit user page) ---
USER_ROLES: tuple[str, ...] = ("Admin", "User", "Super")
# Subset of USER_ROLES that grant admin UI/API access.
ADMIN_ROLES: tuple[str, ...] = ("Admin", "Super")

# --- SMTP (non-secret port / TLS / legacy port 25) ---
SMTP_ALLOW_LEGACY_PORT25_FALLBACK: bool = True

# --- Production / Connect preset (uncomment and adjust for your deployment) ---
# MIN_PASSWORD_LENGTH = 8
# USER_COMMAND_FIELD_ENABLED = True
# DIRECTORY_ATTRIBUTE_PROFILE = "extended"
# REGISTRATION_DIRECTORY_LOOKUP_ENABLED = True
# REGISTRATION_DIRECTORY_LOOKUP_REQUIRED = True
# REGISTRATION_DIRECTORY_LOOKUP_SUFFIXES = ("example.com",)
# INVITE_ALLOWED_EMAIL_DOMAINS = ("example.com", "your-org.mil")
# AUTH_COOKIE_DEPLOYMENT = "connect"
