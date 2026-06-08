# User Management API

Self-hosted **user directory and authentication**: admins invite users (or enable self-registration), users set passwords via email links, and clients integrate via **JWT bearer tokens** or the **built-in HTML admin UI** on the same port as `/docs`.

**Use it when you need:** invite-based onboarding, password-reset email flows, configurable roles, and optional LDAP/directory enrichment — without building auth from scratch.

**Not a fit if you need:** OAuth/SAML social login, fine-grained RBAC beyond configurable role labels, or a separate SPA frontend (use [`../user_management_streamlit/`](../user_management_streamlit/) for a Streamlit UI).

**Full monorepo setup:** [`../README.md`](../README.md#setup-from-scratch)

| Doc | Purpose |
|-----|---------|
| [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) | 10-minute tutorial: seed → login → invite → accept |
| [`CONFIG.md`](CONFIG.md) | Every `config.py` and `.env` setting |
| [`USER_GUIDE.md`](USER_GUIDE.md) | Day-2 operations, deployment, troubleshooting |
| [`docs/API.md`](docs/API.md) | Full JSON API, errors, JWT claims |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Production hardening checklist |
| [`HTML_UI.md`](HTML_UI.md) | HTML routes, navigation, customization |

Alternate **Streamlit** UI: [`../user_management_streamlit/`](../user_management_streamlit/) with `BACKEND_URL` pointing at this API.

---

## Prerequisites

- **Python 3.10+**
- **Git** and network access for `pip install -r requirements.txt` (installs `fastapi-workbench` from the monorepo Git URL). When developing inside this repository, you can use the local `../fastapi_workbench/` package instead of the Git dependency.

---

## Quickstart (local)

```bash
cd user_management_api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set a strong JWT_SECRET (or use JWT_ALLOW_WEAK_SECRET=1 for local dev)
```

### First login (required)

The database starts **empty** after migrate. Pick one:

**A — Seed an admin (fastest for local dev)**

```bash
SEED_ADMIN_ENABLED=1 SEED_ADMIN_PASSWORD='YourStrongPassword12' alembic upgrade head
JWT_ALLOW_WEAK_SECRET=1 uvicorn app.asgi:app --reload --host 127.0.0.1 --port 8001
```

Sign in at http://127.0.0.1:8001/login with **`admin@example.com`** and the password you set.

**B — Allow your test email domain**

Default [`config.py`](config.py) only allows `socom.mil` and `soc.mil`. For local testing, add domains such as `example.com`:

```python
INVITE_ALLOWED_EMAIL_DOMAINS: tuple[str, ...] = ("example.com", "example.org", "test.local")
```

Then seed an admin (A), sign in, and use **Admin → Invite** (requires SMTP in `.env`).

**C — JSON-only testing**

After seeding (A), use `POST /auth/token` — see [`docs/API.md`](docs/API.md).

If you already ran `alembic upgrade head` without seeding, run the seed command again (migrations are idempotent).

- **HTML UI:** http://127.0.0.1:8001/login
- **OpenAPI:** http://127.0.0.1:8001/docs
- **Health (JSON):** `curl -H 'Accept: application/json' http://127.0.0.1:8001/`

Step-by-step walkthrough: [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md).

---

## HTML UI

Cookie-based sessions power the built-in UI. Navigation is **role-based**:

| User | Lands on | Nav |
|------|----------|-----|
| Guest | `/login` | Register (if enabled), Sign in |
| Non-admin | `/account` | Account |
| Admin | `/admin` | Admin, Account |

Key pages: `/login`, `/register` (when `SELF_REGISTRATION_ENABLED`), `/account`, `/admin`, `/admin/users/{id}` (edit user), `/invites/accept`, `/password/reset`.

`/users` (HTML) redirects to `/admin` or `/account`; user listing is on **Admin** only.

Customize branding, roles, and self-registration in **`config.py`** — see [`CONFIG.md`](CONFIG.md).

### Posit Connect

Embedded Connect iframes may drop cookies. For Connect HTML deployments set in **`config.py`**:

```python
AUTH_COOKIE_DEPLOYMENT: str = "connect"
```

For maximum reliability on Connect, deploy [`../user_management_streamlit/`](../user_management_streamlit/) instead (JWT in Streamlit session state).

---

## JSON API (summary)

| Endpoint | Auth | Notes |
|----------|------|-------|
| `POST /auth/token` | — | Form: `username` (email), `password` → JWT |
| `GET /users/me` | Bearer | Current user (+ `roles`) |
| `PATCH /users/me` | Bearer | Update profile |
| `POST /users/me/password` | Bearer | Change password (invalidates token) |
| `GET /users` | Bearer (admin) | List users (JSON); browser cookie → redirect |
| `POST /invites` | Bearer (admin) | Create invite |
| `POST /invites/lookup` | Bearer (admin) | Directory preview for invite UI |
| `POST /invites/inspect` | Bearer (admin) | Inspect invite token metadata |
| `POST /invites/accept` | — | Accept invite + set password |
| `POST /register` | — | Self-registration (form; see API doc) |
| `POST /password/forgot` | — | Request reset (non-enumerating) |
| `POST /password/inspect` | — | Inspect reset token metadata |
| `POST /password/reset` | — | Complete reset |
| `PATCH /admin/users/{id}` | Bearer (admin) | Update user (prefer `roles`) |
| `DELETE /admin/users/{id}` | Bearer (admin) | Delete user |
| `GET /__meta` | — | Proxy/UI base-path metadata |

Full reference: [`docs/API.md`](docs/API.md).

Example:

```bash
TOKEN="$(curl -sS -X POST http://127.0.0.1:8001/auth/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin@example.com&password=YourStrongPassword12' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')"

curl -sS http://127.0.0.1:8001/users/me -H "Authorization: Bearer $TOKEN"
```

---

## Configuration

**Tunables** → edit [`config.py`](config.py) only (branding, roles, rate limits, cookies, invite domains, `SELF_REGISTRATION_ENABLED`, etc.).

**Secrets** → copy [`.env.example`](.env.example) to `.env` (`DATABASE_URL`, `JWT_SECRET`, SMTP, directory URL).

Full reference: [`CONFIG.md`](CONFIG.md). Production checklist: [`docs/SECURITY.md`](docs/SECURITY.md).

---

## Workbench / reverse proxy

Behind Posit Workbench or a path prefix, use the runner:

```bash
cd user_management_api
python run_workbench.py
```

Workbench helpers live in [`../fastapi_workbench/`](../fastapi_workbench/). Set `BASE_PATH` and `PUBLIC_BASE_URL` in **`config.py`** for correct invite/reset links.

---

## Seeding users

Migrations are **opt-in** at `alembic upgrade head` time (env vars in `.env` or shell):

**Admin** (`0002_seed_admin`):

```bash
SEED_ADMIN_ENABLED=1 SEED_ADMIN_PASSWORD='your-strong-password' alembic upgrade head
```

**Non-admin** (`0003_seed_user`) — requires both `SEED_USER_EMAIL` and `SEED_USER_PASSWORD` (min 12 chars).

---

## Development checks

From `user_management_api/`:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q tests
```

From repo root (format, lint, typecheck):

```bash
ruff format --check user_management_api
ruff check user_management_api
ty check user_management_api
```

Or use `./run_tests.sh` inside `user_management_api/`.
