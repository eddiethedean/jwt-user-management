# User guide: `user_management_api`

This guide explains how to **run**, **use**, and **deploy** the FastAPI backend in `user_management_api/`.

## What this service does

- **User management** (create/update/deactivate users)
- **JWT authentication** (`/auth/token` issues bearer tokens)
- **Invites** (admin generates invite links; users accept invites)
- **Password resets** (request reset link; set a new password)

The browser UI is **always built into this service** (login, register, admin, invites, password reset).

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
uvicorn app.asgi:app --reload --port 8001
```

- **HTML UI**: `http://127.0.0.1:8001/` (redirects to `/register`)
- **API docs**: `http://127.0.0.1:8001/docs`

## Configuration (`.env` and `config.py`)

Copy **`.env.example`** to **`.env`** for secrets and deployment endpoints (**`DATABASE_URL`**, **`JWT_SECRET`**, SMTP, **`DIRECTORY_LOOKUP_URL`**, etc.).

### Tunables in `config.py`

- **`PUBLIC_BASE_URL`**: used to generate invite/reset links (e.g. `http://127.0.0.1:8001`)
- **`BASE_PATH`**: optional external path prefix when behind a reverse proxy (e.g. `/connect/app`)

- **`DATABASE_URL`**: default `sqlite:///./app.db`

### Secrets (required for real deployments)

- **`JWT_SECRET`**: JWT signing key (use a strong secret outside `ENVIRONMENT=dev`)
- **`SESSION_SECRET`**: admin web session cookie signing secret (use a strong secret outside `ENVIRONMENT=dev`)

### Optional email sending

- **`SMTP_*`**: send invite/reset emails

### Optional Azure AD validation

- **`AZURE_*`**: if set, invite acceptance and invite creation can validate emails against your tenant

### Airgapped / offline mode

If deployed on an airgapped intranet with no internet access, set:

- **`OFFLINE_MODE=true`**

This disables outbound SaaS integrations (notably Azure AD / Microsoft Graph validation), while keeping intranet integrations like SMTP available.

## How to use the API

### 1) Obtain a JWT

`POST /auth/token` uses **form data** (OAuth2 password flow shape):

```bash
curl -sS -X POST "http://127.0.0.1:8001/auth/token" \
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
curl -sS "http://127.0.0.1:8001/users/me" \
  -H "Authorization: Bearer $TOKEN"
```

### 3) Admin endpoints

Admin routes require a JWT whose claims include **`is_admin: true`** (set at login/token issuance). Listing all users: `GET /users` (admin only).

### JWT session model

- Cookie and Bearer auth validate the JWT signature and expiry **without a database round-trip**.
- **`is_active`** and **`is_admin`** in the database apply when **issuing** a new token (login). Changes after login take effect on the next login, or when the JWT expires.
- Shorten **`JWT_EXPIRES_MINUTES`** in **`config.py`** if you need faster effective revocation.

## HTML UI

Open `/login`, `/register`, `/users`, `/admin`, and related pages on the same origin as the API. Emailed invite and reset links use **`PUBLIC_BASE_URL`** with paths such as `/invites/accept?token=...`.

On **Posit Connect**, set **`AUTH_COOKIE_DEPLOYMENT = "connect"`** in **`config.py`** so auth cookies work in embedded contexts.

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

- API: `POST /invites/accept`

## Password reset

### Request a reset link

`POST /password/forgot` always returns `ok=true` (to avoid account enumeration).

### Reset password

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
BACKEND_PORT=8001 \
PROXY_PREFIX=/connect/app \
PROXY_MODE=preserve \
PROXY_PORT=8080 \
docker compose -f infra/connect-proxy/docker-compose.yml up
```

Then access the API, for example:

- `http://127.0.0.1:8080/connect/app/docs`

Set **`PUBLIC_BASE_URL`** in **`config.py`** to the browser-visible API base URL (for the example above, `http://127.0.0.1:8080/connect/app`) so emailed links and redirects resolve correctly.

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

- **Invite/reset links point to the wrong place**: set `PUBLIC_BASE_URL` and `BASE_PATH` correctly for your deployment.
- **Running behind a proxy**: ensure the proxy forwards `X-Forwarded-*` headers and (for strip mode) sets `X-Forwarded-Prefix`.
- **Airgapped intranet**: set `OFFLINE_MODE=true` and do not set `AZURE_*`.
