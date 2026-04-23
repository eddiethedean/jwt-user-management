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

```bash
The backend serves the admin UI at `/admin/` (it runs Streamlit internally).

- Admin UI: `http://localhost:8000/admin/`
```

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
- `JWT_SECRET`: secret used to sign JWTs (use a strong secret outside `ENVIRONMENT=dev`)
- `JWT_EXPIRES_MINUTES`: default `60`
- `ADMIN_API_KEY`: if set, Streamlit can call admin endpoints via `X-Admin-Api-Key`
- `SMTP_*`: optional SMTP settings to send invite emails
- `AZURE_*`: optional Azure AD (Microsoft Graph) settings to validate emails
- `RATE_LIMIT_ENABLED`: optional (default true) in-memory rate limiting for sensitive endpoints
- `RATE_LIMIT_TRUST_PROXY_HEADERS`: optional; only enable if you trust your proxy headers

### Streamlit admin (`user_management_api/admin_ui/.env`)

- `BACKEND_URL`: e.g. `http://localhost:8000`
- `BACKEND_ADMIN_API_KEY`: must match backend `ADMIN_API_KEY`

## Notes on Azure AD / Active Directory validation

The backend includes an optional Microsoft Graph integration (client credentials flow) that can validate that an email exists in your tenant.
Set `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` to enable it.

## Run tests

Backend:

```bash
cd user_management_api
source .venv/bin/activate
pytest
```

Streamlit apps:

```bash
cd user_management_api/admin_ui
source .venv/bin/activate
pytest
```

```bash
cd streamlit_user
source .venv/bin/activate
pytest
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

