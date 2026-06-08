# User Management API

FastAPI + SQLModel + Alembic service with **JWT authentication**, **invite and password-reset flows**, and a **server-rendered HTML UI** on the same port as `/docs`.

**Full from-scratch setup (repo root):** [`../README.md`](../README.md#setup-from-scratch)

| Doc | Purpose |
|-----|---------|
| [`CONFIG.md`](CONFIG.md) | Every `config.py` and `.env` setting |
| [`USER_GUIDE.md`](USER_GUIDE.md) | Run, deploy, HTML flows, API usage |
| [`HTML_UI.md`](HTML_UI.md) | HTML routes, navigation, customization |

An alternate **Streamlit** UI lives in [`../user_management_streamlit/`](../user_management_streamlit/) — run it separately with `BACKEND_URL` pointing at this API.

---

## Quickstart (local)

Prereqs: **Python 3.10+**.

```bash
cd user_management_api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set a strong JWT_SECRET (or use JWT_ALLOW_WEAK_SECRET=1 for local dev)
alembic upgrade head
JWT_ALLOW_WEAK_SECRET=1 uvicorn app.asgi:app --reload --host 127.0.0.1 --port 8001
```

- **HTML UI:** http://127.0.0.1:8001/login  
- **OpenAPI:** http://127.0.0.1:8001/docs  
- **Health (JSON):** `curl -H 'Accept: application/json' http://127.0.0.1:8001/`

After migrate, optionally seed users — see [Seeding users](#seeding-users) below.

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
| `POST /users/me/password` | Bearer | Change password |
| `GET /users` | Bearer (admin) | List users (JSON); browser cookie → redirect |
| `POST /invites` | Bearer (admin) | Create invite |
| `POST /invites/accept` | — | Accept invite + set password |
| `POST /password/forgot` | — | Request reset (non-enumerating) |
| `POST /password/reset` | — | Complete reset |
| `PATCH /admin/users/{id}` | Bearer (admin) | Update user (incl. `roles`) |
| `DELETE /admin/users/{id}` | Bearer (admin) | Delete user |

Example:

```bash
TOKEN="$(curl -sS -X POST http://127.0.0.1:8001/auth/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=user@example.com&password=your-password' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')"

curl -sS http://127.0.0.1:8001/users/me -H "Authorization: Bearer $TOKEN"
```

---

## Configuration

**Tunables** → edit [`config.py`](config.py) only (branding, roles, rate limits, cookies, invite domains, `SELF_REGISTRATION_ENABLED`, etc.).

**Secrets** → copy [`.env.example`](.env.example) to `.env` (`DATABASE_URL`, `JWT_SECRET`, SMTP, directory URL).

Full reference: [`CONFIG.md`](CONFIG.md).

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
