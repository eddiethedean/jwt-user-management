# Backend (bare-bones)

Minimal FastAPI + SQLModel + Alembic app with:
- **HTML forms**: register + login + user list page
- **JWT auth**: obtain token via form login or API token endpoint
- **SQLite** persistence

## Run locally

Prereqs: **Python 3.10+**.

```bash
cd user_management_api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

- Docs: `http://127.0.0.1:8001/docs`

## HTML pages

- Register: `GET /register`
- Login: `GET /login`
- Users page: `GET /users?token=...` (paste token from `/login`)
- Admin page: `GET /admin?token=...` (paste token from `/login`)

## JSON API

- JWT token: `POST /auth/token` (form-encoded: `username` = email, `password`)
- Current user: `GET /users/me` (Bearer)
- List users: `GET /users` (Bearer)

Example:

```bash
TOKEN="$(curl -sS -X POST http://127.0.0.1:8001/auth/token \\
  -H 'Content-Type: application/x-www-form-urlencoded' \\
  -d 'username=test@example.com&password=pass' | python -c 'import sys, json; print(json.load(sys.stdin)[\"access_token\"])')"

curl -H \"Authorization: Bearer $TOKEN\" http://127.0.0.1:8001/users/me
```

## Environment

Configured via `user_management_api/.env`:

- `DATABASE_URL`: e.g. `sqlite:///./app.db`
- `BASE_PATH`: optional external path prefix when served behind a reverse proxy (e.g. Workbench)
- `JWT_SECRET`: secret used to sign JWTs
- `JWT_EXPIRES_MINUTES`: default `60`
- `JWT_ALGORITHM`: default `HS256`

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
