# User guide: `user_management_api`

This guide explains how to **run**, **use**, and **deploy** the FastAPI backend in `user_management_api/`.

## What this service does

- **User management** (create/update/deactivate users)
- **JWT authentication** (`/auth/token` issues bearer tokens)
- **Invites** (admin generates invite links; users accept invites)
- **Password resets** (request reset link; set a new password)

The browser UI is the **Streamlit** app in `../user_management_streamlit/`, run as a **separate process** with `BACKEND_URL` pointing at this API.

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

- **API docs**: `http://127.0.0.1:8001/docs`

Run the Streamlit UI from `../user_management_streamlit/` separately; set `BACKEND_URL` there to this API (see that folder’s README).

## Configuration (`.env` and `config.py`)

Copy **`.env.example`** to **`.env`** for secrets and deployment endpoints (**`DATABASE_URL`**, **`JWT_SECRET`**, SMTP, **`DIRECTORY_LOOKUP_URL`**, etc.).

### Tunables in `config.py`

- **`PUBLIC_BASE_URL`**: used to generate invite/reset links (e.g. `http://127.0.0.1:8001`)
- **`BASE_PATH`**: optional external path prefix when behind a reverse proxy (e.g. `/connect/app`)
- **`UI_PUBLIC_BASE_URL`**: optional Streamlit origin for emailed deep links (see root README)

### Core settings (`.env`)

- **`DATABASE_URL`**: default `sqlite:///./app.db`

### Secrets (required for real deployments)

- **`JWT_SECRET`**: JWT signing key (use a strong secret outside `ENVIRONMENT=dev`)
- **`SESSION_SECRET`**: admin web session cookie signing secret (use a strong secret outside `ENVIRONMENT=dev`)

### Admin access

- **`ADMIN_API_KEY`**: if set, allows admin API access via header `X-Admin-Api-Key`

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

Admin authorization is either:

- **Admin JWT** (a user with `is_admin=true`), OR
- **`X-Admin-Api-Key`** matching `ADMIN_API_KEY`

Example: list users with an admin API key:

```bash
curl -sS "http://127.0.0.1:8001/users" \
  -H "X-Admin-Api-Key: $ADMIN_API_KEY"
```

## UI

This service is API-first. The legacy HTML UI (including `/admin/`, `/login`, etc.)
was archived because cookie-based sessions proved unreliable in embedded Posit
Connect contexts.

The supported UI is the Streamlit app in `../user_management_streamlit/`. Run it as its own Streamlit process and set **`BACKEND_URL`** to the URL of this API (include any path prefix the API is served under).

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

Run the Streamlit app in `../user_management_streamlit/` as a separate process. Set `BACKEND_URL` to the browser-visible API base URL (for the example above, `http://127.0.0.1:8080/connect/app`).

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
