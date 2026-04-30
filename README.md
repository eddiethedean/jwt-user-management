# JWT User Management (bare-bones)

This repo contains:

- `user_management_api/`: **Bare-bones FastAPI + SQLModel + Alembic** backend with **JWT auth** and **simple HTML forms** (register/login/users page).
- `streamlit_user/`: Streamlit demo that logs in against the backend.
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
uvicorn app.main:app --reload --port 8001
```

API docs: `http://localhost:8001/docs`

### 2) Streamlit user demo

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
 
