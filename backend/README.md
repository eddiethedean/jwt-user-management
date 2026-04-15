# Backend (FastAPI + SQLModel + Alembic)

FastAPI API for user management, JWT issuance, invites, and password resets.

## Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- API docs: `http://127.0.0.1:8000/docs`

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

Configured via `backend/.env`:

- `DATABASE_URL`: e.g. `sqlite:///./app.db`
- `PUBLIC_BASE_URL`: used to generate invite/reset links (e.g. `http://localhost:8000`)
- `JWT_SECRET`: JWT signing key (rotate if compromised)
- `ADMIN_API_KEY`: admin key used by `streamlit_admin` (rotate if compromised)
- `SMTP_*`: send invite/reset emails
- `AZURE_*`: optional Microsoft Graph (Azure AD) validation

