# User Management API

**Full from-scratch setup:** see the repository root [`README.md`](../README.md#setup-from-scratch).

FastAPI + SQLModel + Alembic service with:

- **Built-in HTML UI** — login, register, admin, account, invites, password reset (cookie auth)
- **JSON API** — JWT Bearer auth for programmatic clients (`/docs`)
- **SQLite** (or PostgreSQL) persistence

## Run locally

Prereqs: **Python 3.10+**.

```bash
cd user_management_api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.asgi:app --reload --port 8001
```

- HTML UI: `http://127.0.0.1:8001/` (redirects to `/register`)
- OpenAPI: `http://127.0.0.1:8001/docs`

## HTML UI (browser app)

The built-in HTML app runs on the **same port** as the JSON API.

1. Start the server (see [Run locally](#run-locally) above).
2. Open a browser at **`http://127.0.0.1:8001/`** — you are redirected to **`/register`**.
3. Sign in at **`http://127.0.0.1:8001/login`**.

After seeding (`alembic upgrade head`), use the default admin account:

- Email: `admin@example.com`
- Password: `admin123`

| Page | URL | Who |
|------|-----|-----|
| Register | `/register` | Guest (self-registration) |
| Sign in | `/login` | Guest |
| Account | `/account` | Signed-in user |
| Admin | `/admin` | Admin |
| Accept invite | `/invites/accept?token=…` | Guest (from email link) |
| Reset password | `/password/reset?token=…` | Guest (from email link) |

Admins land on `/admin` after login; everyone else goes to `/account`. Static assets (CSS/JS) are at `/static`.

Behind Workbench or a path prefix, prepend your mount path (for example `/s/<service>/p/<project>/login`). See [Run on Workbench](#run-on-workbench-behind-a-proxy-prefix) and set **`BASE_PATH`** / **`PUBLIC_BASE_URL`** in **`config.py`** so links and redirects stay correct.

More detail: [`HTML_UI.md`](HTML_UI.md) and [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md).

For **Posit Connect** embedded HTML, set **`AUTH_COOKIE_DEPLOYMENT = "connect"`** in **`config.py`** (see the production preset block).

## Run on Workbench (behind a proxy prefix)

If you’re running behind Posit Workbench / RStudio Server (URLs like `/s/<service>/p/<project>/...`),
use the runner script so Uvicorn is started with the correct `root_path`:

```bash
cd user_management_api
python run_workbench.py
```

Notes:

- Workbench path normalization and external URL building live in **`fastapi_workbench/`** at the repo root.
- If Workbench sets `RS_SERVER_URL`, the runner may infer the prefix via `rserver-url`.
- Set `BASE_PATH=/s/<service>/p/<project>` explicitly when needed.
- Override the port with `PORT=8001` (otherwise a free port is chosen).
- Set **`PUBLIC_BASE_URL`** in **`config.py`** so emailed invite/reset links use a browser-routable host.

**`/login` returns `{"detail":"Not Found"}` but `/docs` works?** You are likely on an older build (before HTML routes lived in this API) or started the app without the Workbench entrypoint. **`git pull`**, restart with **`python run_workbench.py`** (or **`uvicorn app.asgi:app`**, not `app.main:app` alone), then open **`/login`** on the same prefixed URL as **`/docs`**. **`/`** should redirect to **`/register`**.

## JSON API

- JWT token: `POST /auth/token` (form-encoded: `username` = email, `password`)
- Current user: `GET /users/me` (Bearer)
- List users: `GET /users` (admin Bearer or admin cookie session)
- Create invite (admin only): `POST /invites` (Bearer; body: `{ "email": "..." }`)
- Accept invite: `POST /invites/accept` (body: `{ "token": "...", "password": "..." }`)

Example:

```bash
TOKEN="$(curl -sS -X POST http://127.0.0.1:8001/auth/token \\
  -H 'Content-Type: application/x-www-form-urlencoded' \\
  -d 'username=test@example.com&password=pass' | python -c 'import sys, json; print(json.load(sys.stdin)[\"access_token\"])')"

curl -H \"Authorization: Bearer $TOKEN\" http://127.0.0.1:8001/users/me
```

## Environment

- **Tunables (no secrets):** `PUBLIC_BASE_URL`, `INVITE_ALLOWED_EMAIL_DOMAINS`, `BASE_PATH`, cookie flags, JWT/password policy, directory attribute profile, registration LDAP gate, Postgres async flags, and optional user profile fields — edit **`config.py`** only. Do not duplicate these keys in **`.env`**.

  For production or Posit Connect, uncomment and adjust the preset block at the bottom of **`config.py`**.

- **Secrets and deployment endpoints:** copy **`.env.example`** to **`.env`** and set **`DATABASE_URL`**, **`JWT_SECRET`**, SMTP credentials if you send mail, **`DIRECTORY_LOOKUP_URL`** / **`DIRECTORY_LOOKUP_CA_BUNDLE`** when you use directory lookup, and **`SEED_*`** if you customize seeding.

### Optional: directory (LDAP) lookup

Use this when an external HTTP service can confirm that an email exists in your directory (for example LDAP-backed APIs on Posit Connect).

1. Set **`DIRECTORY_LOOKUP_URL`** in `.env` to the **base URL** of the lookup service. The backend issues:

   `GET <DIRECTORY_LOOKUP_URL>?query=<url-encoded-email>`

2. The response must be JSON with an **`attributes`** object. Mapping depends on **`DIRECTORY_ATTRIBUTE_PROFILE`** in **`config.py`**:

   - **`generic`:** `displayName` / `cn`; country from `c` / `co` (`C=US` → `US`).
   - **`extended`:** `givenName` + `sn`; country from `extensionAttribute8`; command from `department` (when **`USER_COMMAND_FIELD_ENABLED`**).
   - **`both`:** extended attributes first, then generic fallbacks.

3. **`DIRECTORY_LOOKUP_REQUIRED`**: when `true`, failed directory HTTP responses or invalid JSON from the directory service can cause **`lookup_email`** to raise (used only for optional enrichment). **Invites are not blocked** when the directory returns “not found”. Optional **`REGISTRATION_DIRECTORY_LOOKUP_*`** settings can require a directory match for self-registration on configured email suffixes.

4. Other knobs: **`DIRECTORY_LOOKUP_TIMEOUT_S`**, **`DIRECTORY_LOOKUP_VERIFY_SSL`** — booleans and timeout are defined in **`config.py`**. **`DIRECTORY_LOOKUP_CA_BUNDLE`** is a filesystem path and belongs in **`.env`** only.

5. **Invite / registration domains:** edit the **`INVITE_ALLOWED_EMAIL_DOMAINS`** tuple in **`config.py`** (defaults **`example.com`**, **`example.org`**).

The admin **`POST /invites/lookup`** preview returns directory **country** (and display fields) when the service responds; if the service is disabled or errors, the response still succeeds with empty strings.

### Optional: SMTP (invites, self-registration, password reset)

Set **`SMTP_HOST`** and **`SMTP_FROM_EMAIL`** (and port, TLS, credentials as needed) so the API can send **invite**, **self-registration setup**, and **password reset** emails. If SMTP is not configured, invite and reset flows still create tokens and return URLs in API responses; email calls are skipped where implemented as no-ops. When SMTP is configured but sending fails, the server logs an error (without changing the non-enumerating JSON responses for forgot-password).

Emailed links use **`PUBLIC_BASE_URL`** with paths such as `/invites/accept?token=...` and `/password/reset?token=...`.

### Seed an initial admin user (optional)

On `alembic upgrade head`, a default admin account is created if it doesn't exist:

- Email: `admin@example.com`
- Password: `admin123`

You can override these with:

- `SEED_ADMIN_EMAIL`
- `SEED_ADMIN_PASSWORD`

## Run tests

In some environments, globally installed pytest plugins can break test runs. Use:

```bash
cd user_management_api
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests
```
