# User guide: `user_management_api`

This guide explains how to **run**, **use**, and **deploy** the FastAPI backend in `user_management_api/`.

## What this service does

- **User management** (create/update/deactivate users)
- **JWT authentication** (`/auth/token` issues bearer tokens)
- **Invites** (admin generates invite links; users accept invites)
- **Password resets** (request reset link; set a new password)
- **Admin Web UI** at `/admin/` (session + CSRF protected)

## Prerequisites

- Python **3.10+**
- A virtual environment tool (built-in `venv` is fine)

## Quickstart (local, SQLite)

From repo root:

```bash
cd user_management_api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- **API docs**: `http://127.0.0.1:8000/docs`
- **Admin UI**: `http://127.0.0.1:8000/admin/`

## Configuration (`.env`)

Edit `user_management_api/.env` (copy from `.env.example`).

### Core settings

- **`DATABASE_URL`**: default `sqlite:///./app.db`
- **`PUBLIC_BASE_URL`**: used to generate invite/reset links (e.g. `http://localhost:8000`)
- **`BASE_PATH`**: optional external path prefix when behind a reverse proxy (e.g. `/connect/app`)
- **`ENVIRONMENT`**: `dev` or `prod`

### Secrets (required for real deployments)

- **`JWT_SECRET`**: JWT signing key (use a strong secret outside `ENVIRONMENT=dev`)
- **`SESSION_SECRET`**: admin web session cookie signing secret (use a strong secret outside `ENVIRONMENT=dev`)

### Admin access

- **`ADMIN_API_KEY`**: if set, allows admin API access via header `X-Admin-Api-Key`

### Optional email sending

- **`SMTP_*`**: send invite/reset emails

### Optional Azure AD validation

- **`AZURE_*`**: if set, invite acceptance and invite creation can validate emails against your tenant

## How to use the API

### 1) Obtain a JWT

`POST /auth/token` uses **form data** (OAuth2 password flow shape):

```bash
curl -sS -X POST "http://127.0.0.1:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=your-password"
```

Response:

- `access_token`: JWT string
- `token_type`: `bearer`

### 2) Call authenticated endpoints

Example: get current user:

```bash
TOKEN="...jwt..."
curl -sS "http://127.0.0.1:8000/users/me" \
  -H "Authorization: Bearer $TOKEN"
```

### 3) Admin endpoints

Admin authorization is either:

- **Admin JWT** (a user with `is_admin=true`), OR
- **`X-Admin-Api-Key`** matching `ADMIN_API_KEY`

Example: list users with an admin API key:

```bash
curl -sS "http://127.0.0.1:8000/users" \
  -H "X-Admin-Api-Key: $ADMIN_API_KEY"
```

## Admin Web UI (`/admin/`)

The admin UI is served by the backend under `/admin/` and uses:

- **Session auth** (signed cookie)
- **CSRF protection** for state-changing actions
- Same-origin fetch to `/admin/api/*`

### Login

Open:

- `http://127.0.0.1:8000/admin/`

Then sign in with an admin user account.

### Seeding an initial admin user (optional)

When running `alembic upgrade head`, you can seed an initial admin user by setting:

- `SEED_ADMIN_EMAIL`
- `SEED_ADMIN_PASSWORD`
- `SEED_ADMIN_FULL_NAME` (optional)

If the email already exists, the migration does nothing.

## Invites

### Admin creates an invite

`POST /invites` (admin-only). The response includes an `invite_url`.

### User accepts the invite

- HTML page: `GET /invites/accept?token=...`
- API: `POST /invites/accept`

## Password reset

### Request a reset link

`POST /password/forgot` always returns `ok=true` (to avoid account enumeration).

### Reset password

- HTML page: `GET /password/reset?token=...`
- API: `POST /password/reset`

## Running behind a reverse proxy (Posit Connect / Workbench / path prefix)

If the app is served under an external prefix like:

- `https://host/connect/app/...`

set:

- **`BASE_PATH=/connect/app`**
- **`PUBLIC_BASE_URL=https://host`** (or `https://host/connect/app` depending on how you build external links; see below)

### Link generation rule of thumb

- Invite/reset links are generated from **`PUBLIC_BASE_URL + BASE_PATH + /...`**.
- For most reverse proxies, set:
  - `PUBLIC_BASE_URL=https://your-host`
  - `BASE_PATH=/your/prefix`

## Local Connect-like proxy (nginx)

There is a local nginx proxy under `infra/connect-proxy/` to mimic “served behind a prefix”.

Example:

```bash
BACKEND_HOST=host.docker.internal \
BACKEND_PORT=8000 \
PROXY_PREFIX=/connect/app \
PROXY_MODE=preserve \
PROXY_PORT=8080 \
docker compose -f infra/connect-proxy/docker-compose.yml up
```

Then access:

- `http://127.0.0.1:8080/connect/app/docs`
- `http://127.0.0.1:8080/connect/app/admin/`

If your proxy strips the prefix before proxying:

- `PROXY_MODE=strip` (nginx strips prefix and sets `X-Forwarded-Prefix`)

## Development checks

From repo root (using the repo root venv):

```bash
ruff format . && ruff check . && ty check .
```

Run backend tests:

```bash
pytest -q user_management_api/tests
```

Run e2e tests (optional):

```bash
pytest -q e2e
```

Proxy-mode e2e:

```bash
E2E_USE_PROXY=1 E2E_PROXY_MODE=preserve pytest -q e2e
E2E_USE_PROXY=1 E2E_PROXY_MODE=strip pytest -q e2e
```

## Troubleshooting

- **Admin UI redirects to login repeatedly**: confirm `SESSION_SECRET` is set and you’re accessing the app under the same prefix as `BASE_PATH` (if any).\n+- **Invite/reset links point to the wrong place**: set `PUBLIC_BASE_URL` and `BASE_PATH` correctly for your deployment.\n+- **Running behind a proxy**: ensure the proxy forwards `X-Forwarded-*` headers and (for strip mode) sets `X-Forwarded-Prefix`.\n+
