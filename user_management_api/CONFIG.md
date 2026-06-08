# Configuration guide

This app splits configuration into two files:

| File | Purpose | Committed? |
|------|---------|------------|
| **`config.py`** | Tunables, branding, roles, rate limits, cookie policy | Yes — edit and commit |
| **`.env`** | Secrets and deployment endpoints (DB URL, JWT secret, SMTP, directory URL) | No — copy from `.env.example` |

Do **not** duplicate `config.py` keys in `.env`. Values in `config.py` are loaded at startup by `app/core/config.py` into the shared `settings` object.

After changing **`config.py`**, restart the server (`uvicorn` does not reload that file unless you touch Python modules that import it — a restart is safest).

After changing **database schema** (new Alembic revisions), run:

```bash
cd user_management_api
alembic upgrade head
```

---

## `.env` — secrets and endpoints

Copy `.env.example` to `.env` in this directory.

### Required for local dev

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLAlchemy URL (default `sqlite:///./app.db`) |
| `JWT_SECRET` | JWT signing key (min 16 chars; weak values rejected unless `JWT_ALLOW_WEAK_SECRET=1`) |

### Optional — email

| Variable | Description |
|----------|-------------|
| `SMTP_HOST` | SMTP server hostname |
| `SMTP_USERNAME` | SMTP auth user |
| `SMTP_PASSWORD` | SMTP auth password |
| `SMTP_FROM_EMAIL` | From address on outbound mail |

Port, TLS, and fallback behavior are in **`config.py`** (`SMTP_PORT`, `SMTP_USE_TLS`, `SMTP_ALLOW_LEGACY_PORT25_FALLBACK`).

### Optional — directory lookup

| Variable | Description |
|----------|-------------|
| `DIRECTORY_LOOKUP_URL` | Base URL of the LDAP/email directory service |
| `DIRECTORY_LOOKUP_CA_BUNDLE` | Path to a custom CA bundle for TLS verification |

Timeout, required flag, and SSL verify are in **`config.py`**.

### Optional — Alembic seed users (migrate time only)

These are read from the environment **when you run** `alembic upgrade head`, not at API runtime.

**Admin** (`0002_seed_admin`):

| Variable | Description |
|----------|-------------|
| `SEED_ADMIN_ENABLED` | Set to `1` to enable admin seeding |
| `SEED_ADMIN_EMAIL` | Default `admin@example.com` |
| `SEED_ADMIN_PASSWORD` | Required when enabled; min 12 chars; weak passwords rejected |

**Non-admin** (`0003_seed_user`):

| Variable | Description |
|----------|-------------|
| `SEED_USER_EMAIL` | Email for the seeded user |
| `SEED_USER_PASSWORD` | Required when email is set; min 12 chars |

Both seed migrations are idempotent (skip if the email already exists).

### Local dev only

| Variable | Description |
|----------|-------------|
| `JWT_ALLOW_WEAK_SECRET` | Set to `1` to allow short/weak `JWT_SECRET` for local testing |

---

## `config.py` — reference

### URLs / proxy

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_PATH` | `""` | External path prefix behind a reverse proxy (e.g. `/s/.../p/...`) |
| `PUBLIC_BASE_URL` | `http://127.0.0.1:8001` | Base URL for invite/reset links in emails |
| `UI_PUBLIC_BASE_URL` | `""` | Optional Streamlit origin for emailed deep links (`/?page=...&token=...`) |

### JWT (non-secret)

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRES_MINUTES` | `60` | Access token lifetime |

### Auth cookies (HTML UI)

| Variable | Default | Description |
|----------|---------|-------------|
| `COOKIE_DEBUG` | `False` | Show cookie debug panel in HTML UI |
| `AUTH_COOKIE_DEPLOYMENT` | `"local"` | `"local"` or `"connect"` (Posit Connect embedded HTML) |
| `AUTH_COOKIE_SAMESITE` | `"lax"` | `lax`, `strict`, or `none` |
| `AUTH_COOKIE_SECURE` | `None` | `True`/`False` to force; `None` infers from HTTPS in local mode |
| `AUTH_COOKIE_DOMAIN` | `""` | Optional cookie domain |
| `AUTH_COOKIE_PARTITIONED` | `False` | CHIPS partitioned cookies |
| `AUTH_COOKIE_LEGACY` | `False` | Legacy cookie compatibility |

### SMTP (non-credentials)

| Variable | Default | Description |
|----------|---------|-------------|
| `SMTP_PORT` | `25` | SMTP port |
| `SMTP_USE_TLS` | `False` | Use STARTTLS |
| `SMTP_ALLOW_LEGACY_PORT25_FALLBACK` | `False` | Retry on port 25 without TLS after errors |

### Rate limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `True` | Enable in-process rate limits |
| `RATE_LIMIT_AUTH_PER_MINUTE` | `20` | Auth/password attempts per minute per key |
| `RATE_LIMIT_TRUSTED_PROXIES` | `()` | IPs allowed to set `X-Forwarded-For` (empty = never trust) |

In-process limits apply per worker; use proxy-level limits for multi-worker deployments.

### Directory client (non-URL)

| Variable | Default | Description |
|----------|---------|-------------|
| `DIRECTORY_LOOKUP_TIMEOUT_S` | `5` | HTTP timeout in seconds |
| `DIRECTORY_LOOKUP_REQUIRED` | `False` | When `True`, reject **invite creation**, **self-registration**, and **admin HTML invites** if directory lookup fails or returns no match. Does **not** block invite **accept** (country enrichment remains best-effort). See [per-endpoint behavior](../USER_GUIDE.md#directory-ldap-lookup). |
| `DIRECTORY_LOOKUP_VERIFY_SSL` | `True` | Verify TLS certificates |

### Self-registration

| Variable | Default | Description |
|----------|---------|-------------|
| `SELF_REGISTRATION_ENABLED` | `True` | When `False`, hides the Register nav link, removes login-page register link, and returns 403 / redirects away from `/register` |

Invite-only deployments should set:

```python
SELF_REGISTRATION_ENABLED: bool = False
```

### Invites / registration domains

| Variable | Default | Description |
|----------|---------|-------------|
| `INVITE_ALLOWED_EMAIL_DOMAINS` | `("socom.mil", "soc.mil")` | Allowed email domain suffixes (after `@`) for invites and self-registration |

### User roles

Roles appear as optional checkboxes on the admin **Edit user** page. Users can hold multiple roles. `is_admin` is synced from `ADMIN_ROLES`.

| Variable | Default | Description |
|----------|---------|-------------|
| `USER_ROLES` | `("Admin", "User", "Super")` | All assignable role labels |
| `ADMIN_ROLES` | `("Admin", "Super")` | Subset of `USER_ROLES` that grant admin UI/API access |

`ADMIN_ROLES` must be a subset of `USER_ROLES` (startup fails otherwise).

**API PATCH:** Prefer `roles` in `PATCH /admin/users/{id}`. Legacy `is_admin` is a shorthand that maps to all `ADMIN_ROLES` (true) or `User` (false) via `apply_user_roles`. See [`docs/API.md`](docs/API.md).

**Example — admin only via `Admin` role:**

```python
USER_ROLES: tuple[str, ...] = ("Admin", "User", "Super")
ADMIN_ROLES: tuple[str, ...] = ("Admin",)
```

**Example — custom role set:**

```python
USER_ROLES: tuple[str, ...] = ("Operator", "Viewer")
ADMIN_ROLES: tuple[str, ...] = ("Operator",)
```

### HTML UI branding

Shown in the top bar of server-rendered pages (`base.html`).

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_TITLE` | `"User Management"` | Main title and default `<title>` |
| `BRAND_TAG` | `"Demo"` | Small pill next to the title; set to `""` to hide |
| `BRAND_TAG_TITLE` | `"Demo app"` | Tooltip on the brand tag |
| `BRAND_STACK` | `("FastAPI", "SQLModel", ...)` | Technology pills under the subtitle |

**Example — production branding:**

```python
APP_TITLE: str = "SOCOM Account Portal"
BRAND_TAG: str = ""
BRAND_TAG_TITLE: str = ""
BRAND_STACK: tuple[str, ...] = ("FastAPI", "PostgreSQL")
```

### Alembic (committed default)

| Variable | Default | Description |
|----------|---------|-------------|
| `SEED_ADMIN_ENABLED` | `False` | Documented default; actual seeding still requires `SEED_ADMIN_ENABLED=1` in env at migrate time |

---

## Quick start

See [`README.md`](README.md#quickstart-local) and the step-by-step [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) tutorial.

Checklist highlights:

1. `cp .env.example .env` and set `JWT_SECRET`
2. Edit `config.py`: `INVITE_ALLOWED_EMAIL_DOMAINS`, branding, roles
3. Seed admin: `SEED_ADMIN_ENABLED=1 SEED_ADMIN_PASSWORD='...' alembic upgrade head`
4. Start uvicorn (see README)

## Related docs

- [`README.md`](README.md) — quickstart, first login, API summary
- [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) — 10-minute tutorial
- [`docs/API.md`](docs/API.md) — JSON API and error codes
- [`docs/SECURITY.md`](docs/SECURITY.md) — production checklist
- [`USER_GUIDE.md`](USER_GUIDE.md) — HTML flows, deployment, troubleshooting
- [`HTML_UI.md`](HTML_UI.md) — pages, navigation, HTML security
