# JWT User Management (FastAPI + Streamlit Admin)

This repo contains:

- `user_management_api/`: FastAPI API using SQLModel for user management + JWT issuance.
- `user_management_api/admin_ui/`: Streamlit admin UI (now served behind the backend at `/admin/`).
- `streamlit_user/`: Streamlit demo of a user-facing app (login + forgot/reset password) using the backend.

App-specific READMEs:
- `user_management_api/README.md`
- `user_management_api/admin_ui/README.md`
- `streamlit_user/README.md`

## Quickstart (local, SQLite)

Prereqs: **Python 3.10+** (the pinned dependencies and tests may not work on Python 3.8/3.9).

### 1) Backend

```bash
cd user_management_api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

### 2) Admin UI

The backend serves the admin UI at `/admin/` (it runs Streamlit internally).

- Admin UI: `http://localhost:8000/admin/`

### 3) Streamlit user demo

```bash
cd streamlit_user
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py --server.port 8502
```

User demo: `http://localhost:8502`

## Environment

### Backend (`user_management_api/.env`)

- `DATABASE_URL`: e.g. `sqlite:///./app.db`
- `PUBLIC_BASE_URL`: used to generate invite links (e.g. `http://localhost:8000`)
- `BASE_PATH`: optional external path prefix when served behind a reverse proxy (e.g. Workbench). Example: `/s/<service>/p/<project>`
- `JWT_SECRET`: secret used to sign JWTs (use a strong secret outside `ENVIRONMENT=dev`)
- `JWT_EXPIRES_MINUTES`: default `60`
- `ADMIN_API_KEY`: if set, Streamlit can call admin endpoints via `X-Admin-Api-Key`
- `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD`, `SEED_ADMIN_FULL_NAME`: optional admin seed during `alembic upgrade head` (idempotent)
- `SMTP_*`: optional SMTP settings to send invite emails
- `AZURE_*`: optional Azure AD (Microsoft Graph) settings to validate emails
- `RATE_LIMIT_ENABLED`: optional (default true) in-memory rate limiting for sensitive endpoints
- `RATE_LIMIT_TRUST_PROXY_HEADERS`: optional; only enable if you trust your proxy headers
- `ADMIN_UI_REQUIRE_JWT`: optional. If set (`1`/`true`/`yes`), the `/admin/*` reverse proxy requires an admin JWT for HTTP + websocket.
- `ADMIN_UI_LOG_FILE`: optional. Where the embedded Streamlit subprocess writes logs (default: `admin.nohup.log` in repo root).
- `ADMIN_UI_READY_WAIT_S`: optional. Bounded startup wait (seconds) for Streamlit health endpoint to avoid initial `/admin` 502s.

### Streamlit apps (`streamlit_user/.env`, optional)

- `BACKEND_URL`: e.g. `http://localhost:8000`

## Notes on Azure AD / Active Directory validation

The backend includes an optional Microsoft Graph integration (client credentials flow) that can validate that an email exists in your tenant.
Set `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` to enable it.

## Run tests

```bash
source .venv/bin/activate
python -m pytest
```

Static checks:

```bash
ruff format . && ruff check . && ty check .
```

## Migrations (Alembic)

Create a new migration:

```bash
cd user_management_api
source .venv/bin/activate
alembic revision --autogenerate -m "your message"
```

Apply migrations (database initialization):

```bash
alembic upgrade head
```

