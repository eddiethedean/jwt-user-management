# Backend (bare-bones)

**Full from-scratch setup:** see the repository root [`README.md`](../README.md#setup-from-scratch) (Option A for API + Streamlit, Option B for FluxLit only).

Minimal FastAPI + SQLModel + Alembic app with:
- **JWT auth**: obtain token via form login or API token endpoint
- **SQLite** persistence

The browser UI is the **separate** Streamlit app in `../user_management_streamlit/`; configure it with **`BACKEND_URL`** pointing at this API.

## Posit Connect note (HTML UI)

This backend previously included a legacy HTML UI, but when deployed to **Posit Connect** the browser often does **not** persist the login cookie in the embedded Connect context. The legacy HTML UI is now archived under `app/web/archive/`.

For Connect deployments, deploy **`user_management_streamlit/`** as its own Streamlit content (JWT in Streamlit session state) and set **`BACKEND_URL`** to the public URL of this API.

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

- Docs: `http://127.0.0.1:8001/docs`

Start the Streamlit UI separately (see `../user_management_streamlit/README.md`); set `BACKEND_URL=http://127.0.0.1:8001` (or your deployed API URL).

## Run on Workbench (behind a proxy prefix)

If you’re running behind Posit Workbench / RStudio Server (URLs like `/s/<service>/p/<project>/...`),
use the runner script so Uvicorn is started with the correct `root_path`:

```bash
cd user_management_api
python run_workbench.py
```

Notes:
- The Workbench-specific logic (path normalization, safe redirects, external URL building) lives in the reusable package `fastapi_workbench/` at the repo root.
- If Workbench sets `RS_SERVER_URL`, the runner calls `rserver-url` to infer the prefix automatically.
- You can also set `BASE_PATH=/s/<service>/p/<project>` explicitly.
- You can override the port with `PORT=8001` (otherwise a free port is chosen).
- For browser-routable invite links, set `PUBLIC_BASE_URL=https://<your-workbench-host>` in **`config.py`** (the runner may still set the process **`PUBLIC_BASE_URL`** environment variable when `rserver-url` returns a full external URL for workbench URL helpers).

## HTML pages

The legacy HTML UI is archived and no longer served.

## JSON API

- JWT token: `POST /auth/token` (form-encoded: `username` = email, `password`)
- Current user: `GET /users/me` (Bearer)
- List users: `GET /users` (Bearer)
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

- **Tunables (no secrets):** `PUBLIC_BASE_URL`, `UI_PUBLIC_BASE_URL`, `INVITE_ALLOWED_EMAIL_DOMAINS`, `BASE_PATH`, cookie flags, `JWT_ALGORITHM`, `JWT_EXPIRES_MINUTES`, SMTP port/TLS defaults, directory timeout/required/verify flags — edit **`config.py`** in this directory (`user_management_api/config.py`) only. Do not duplicate these keys in **`.env`**.

- **Secrets and deployment endpoints:** copy **`.env.example`** to **`.env`** and set **`DATABASE_URL`**, **`JWT_SECRET`**, SMTP credentials if you send mail, **`DIRECTORY_LOOKUP_URL`** / **`DIRECTORY_LOOKUP_CA_BUNDLE`** when you use directory lookup, and **`SEED_*`** if you customize seeding.

### Optional: directory (LDAP) lookup

Use this when an external HTTP service can confirm that an email exists in your directory (for example LDAP-backed APIs on Posit Connect).

1. Set **`DIRECTORY_LOOKUP_URL`** in `.env` to the **base URL** of the lookup service. The backend issues:

   `GET <DIRECTORY_LOOKUP_URL>?query=<url-encoded-email>`

2. The response must be JSON with an **`attributes`** object. The backend reads:

   - **Email:** `attributes.mail` or `attributes.userPrincipalName` (string or first element of an array).
   - **Display name:** optional `displayName` or `cn`.
   - **Country:** optional `c` or `co`. Values like `C=US` are normalized to `US` for storage and JWT claims.

3. **`DIRECTORY_LOOKUP_REQUIRED`**: when `true`, failed directory HTTP responses or invalid JSON from the directory service can cause **`lookup_email`** to raise (used only for optional enrichment). **Invites and self-registration are not blocked** when the directory returns “not found”; directory data is used to set **`user.country`** (and related fields) when a user **accepts** an invite if a record is available.

4. Other knobs: **`DIRECTORY_LOOKUP_TIMEOUT_S`**, **`DIRECTORY_LOOKUP_VERIFY_SSL`** — booleans and timeout are defined in **`config.py`**. **`DIRECTORY_LOOKUP_CA_BUNDLE`** is a filesystem path and belongs in **`.env`** only.

5. **Invite / registration domains:** edit the **`INVITE_ALLOWED_EMAIL_DOMAINS`** tuple in **`config.py`** (defaults **`socom.mil`**, **`soc.mil`**). Add suffixes such as **`example.com`** for local demos.

The admin **`POST /invites/lookup`** preview returns directory **country** (and display fields) when the service responds; if the service errors or is disabled, the response still succeeds with empty strings.

### Optional: SMTP (invites, self-registration, password reset)

Set **`SMTP_HOST`** and **`SMTP_FROM_EMAIL`** (and port, TLS, credentials as needed) so the API can send **invite**, **self-registration setup**, and **password reset** emails. If SMTP is not configured, invite and reset flows still create tokens and return URLs in API responses; email calls are skipped where implemented as no-ops. When SMTP is configured but sending fails, the server logs an error (without changing the non-enumerating JSON responses for forgot-password).

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
