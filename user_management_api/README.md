# Backend (FastAPI + SQLModel + Alembic)

FastAPI API for user management, JWT issuance, invites, and password resets.

## Run locally

Prereqs: **Python 3.10+**.

```bash
cd user_management_api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- API docs: `http://127.0.0.1:8000/docs`
- Admin UI: `http://127.0.0.1:8000/admin/` (served by backend; server-rendered HTML + JS)

## Key endpoints

- **JWT login**: `POST /auth/token` (form-encoded: `username` = email, `password`)
- **Users (admin)**: `GET /users`, `POST /users`, `PATCH /users/{id}`, `DELETE /users/{id}`
  - Admin auth is either:
    - Bearer JWT for a backend user with `is_admin=true`, OR
    - `X-Admin-Api-Key` header matching `ADMIN_API_KEY`
- **Invites**:
  - Admin creates invite: `POST /invites`
  - User accepts invite:
    - HTML page: `GET /invites/accept?token=...`
    - API: `POST /invites/accept`
- **Password reset**:
  - Request reset email (non-enumerating): `POST /password/forgot`
  - Reset:
    - HTML page: `GET /password/reset?token=...`
    - API: `POST /password/reset`

## Environment

Configured via `user_management_api/.env`:

- `DATABASE_URL`: e.g. `sqlite:///./app.db`
- `PUBLIC_BASE_URL`: used to generate invite/reset links (e.g. `http://localhost:8000`)
- `BASE_PATH`: optional external path prefix when served behind a reverse proxy (e.g. Workbench). Example: `/s/<service>/p/<project>`
- `JWT_SECRET`: JWT signing key (rotate if compromised). Outside `ENVIRONMENT=dev` this must be a strong secret (>=24 chars).
- `SESSION_SECRET`: secret used to sign the admin session cookie. Outside `ENVIRONMENT=dev` this must be a strong secret (>=24 chars).
- `ADMIN_API_KEY`: admin key (rotate if compromised)
- `SMTP_*`: send invite/reset emails
- `AZURE_*`: optional Microsoft Graph (Azure AD) validation
- `RATE_LIMIT_ENABLED`: optional (default true). In-memory rate limiting for sensitive endpoints (login/reset/invite accept).
- `RATE_LIMIT_TRUST_PROXY_HEADERS`: optional. Only enable if you trust your proxy headers.

### Seeding an initial admin user (optional)

When running `alembic upgrade head`, you can optionally seed an initial admin user by setting:

- `SEED_ADMIN_EMAIL`
- `SEED_ADMIN_PASSWORD`
- `SEED_ADMIN_FULL_NAME` (optional)

If the email already exists, the migration does nothing.

## Run tests

```bash
cd user_management_api
source .venv/bin/activate
pytest
```

## Admin UI (admin_web)

The backend serves a small server-rendered admin UI under `/admin` that uses:

- **Session auth** (signed cookie; requires `SESSION_SECRET`)
- **CSRF protection** for state-changing admin actions
- **Same-origin fetch** to `/admin/api/*` from `app/static/admin/admin.js`

**URL**: `http://127.0.0.1:8000/admin/`

## Running behind a reverse proxy (Workbench / path prefix)

If your deployment serves the app under a URL prefix like:

- `https://workbench.socom.mil/s/<service>/p/<project>/...`

set `BASE_PATH` to that prefix (the `/s/.../p/...` part). This enables correct routing and ensures the admin UI and HTML form endpoints generate correct links and asset URLs under the same prefix.

Example:

```bash
BASE_PATH=/s/e886e3c9ab5a7f3d86cf3/p/0da13bad
PUBLIC_BASE_URL=https://workbench.socom.mil
uvicorn app.main:app --port 8001 --proxy-headers --forwarded-allow-ips='*'
```

Then the admin UI will be available at:

- `https://workbench.socom.mil/s/e886e3c9ab5a7f3d86cf3/p/0da13bad/admin`
