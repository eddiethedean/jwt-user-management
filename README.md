# JWT User Management (bare-bones)

This repo contains:

- `user_management_api/`: **Bare-bones FastAPI + SQLModel + Alembic** backend with **JWT auth** (API-only).
- `streamlit_user/`: Streamlit UI that logs in against the backend (also mountable under the FastAPI app at **`/app`**).
- `e2e/`: Browser E2E tests (Playwright).
- `fastapi_workbench/`: Reusable helpers for Posit Workbench / RStudio Server proxy prefixes.

App-specific READMEs:
- `user_management_api/README.md`
- `streamlit_user/README.md`
- `e2e/README.md`

## Quickstart (local, SQLite)

Prereqs: **Python 3.10+**.

### 1) Backend

```bash
cd user_management_api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.asgi:app --reload --port 8001
```

API docs: `http://localhost:8001/docs`
UI (Streamlit, served by the same process): `http://localhost:8001/app`

### Hypercorn (optional)

If you want to run under Hypercorn:

```bash
cd user_management_api
source .venv/bin/activate
hypercorn app.asgi:app --bind 127.0.0.1:8001
```

### 2) Streamlit user demo

The Streamlit UI can be run either:
- **Through FastAPI** at `http://localhost:8001/app` (preferred for Connect/Workbench), or
- As a standalone Streamlit process (developer convenience).

```bash
cd streamlit_user
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run user_app.py --server.port 8502
```

User demo: `http://localhost:8502`

## Posit Connect note (HTML UI vs Streamlit)

The backend originally shipped with a server-rendered HTML UI (cookie-based session via `Set-Cookie`).
When deployed to **Posit Connect**, that HTML UI proved unreliable because browsers would not persist the app’s login cookie in the Connect embedded context. We attempted standard mitigations (e.g. `SameSite=None; Secure`, legacy cookies), but cookie persistence still failed.

As a result, we recommend deploying the **Streamlit UI** (`streamlit_user/`) on Connect instead. Streamlit keeps the JWT in server-side session state and avoids browser cookie persistence issues.

## Environment

### Backend (`user_management_api/.env`)

- `DATABASE_URL`: e.g. `sqlite:///./app.db`
- `JWT_SECRET`: secret used to sign JWTs
- `JWT_EXPIRES_MINUTES`: default `60`
- `JWT_ALGORITHM`: default `HS256`

### Streamlit apps (`streamlit_user/.env`, optional)

- `BACKEND_URL`: e.g. `http://localhost:8001`

## Run tests

```bash
source .venv/bin/activate
python -m pytest
```

If you only want the backend + `fastapi_workbench` tests (no Streamlit deps), run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q user_management_api/tests fastapi_workbench/tests
```
 
