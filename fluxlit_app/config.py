"""
Bundled FastAPI defaults that are safe to commit (no secrets, no credentials).

``app.core.config.Settings`` reads ``.env`` in this directory and applies environment
variables over these defaults. This module only defines: path/public-base defaults,
SMTP transport flags that are not secrets (port, use TLS), and directory client
behaviour (timeouts and booleans—not the lookup service URL).

Use ``.env`` for ``DATABASE_URL``, all ``JWT_*`` fields, ``DIRECTORY_LOOKUP_URL``,
``DIRECTORY_LOOKUP_CA_BUNDLE``, SMTP host and credentials, ``SEED_*``, and anything
else that is secret or environment-specific (see ``.env.example``).
"""

BASE_PATH: str = ""
PUBLIC_BASE_URL: str = "http://127.0.0.1:8000"

SMTP_PORT: int = 25
SMTP_USE_TLS: bool = False

DIRECTORY_LOOKUP_TIMEOUT_S: int = 5
DIRECTORY_LOOKUP_REQUIRED: bool = False
DIRECTORY_LOOKUP_VERIFY_SSL: bool = False
