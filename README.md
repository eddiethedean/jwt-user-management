# JWT User Management (bare-bones)

This repo contains:

- `user_management_api/`: **Bare-bones FastAPI + SQLModel + Alembic** backend with **JWT auth** (API-only).
- `user_management_ui/`: Streamlit UI that logs in against the backend (**separate process**; set `BACKEND_URL` to the API).
- `e2e/`: Browser E2E tests (Playwright).
- `fastapi_workbench/`: Reusable helpers for Posit Workbench / RStudio Server proxy prefixes.

App-specific READMEs:
- `user_management_api/README.md`
- `user_management_ui/README.md`
- `e2e/README.md`

## Quickstart (local, SQLite)

Prereqs: **Python 3.10+**. You need **two terminals** (or two tabs): one for the API, one for the Streamlit UI.

### Run `user_management_api` and `user_management_ui` together

1. **Install and migrate the API once** (from the repo root or any path):

   ```bash
   cd user_management_api
   python -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env
   # Edit .env if needed: DATABASE_URL, JWT_SECRET, PUBLIC_BASE_URL, etc.
   alembic upgrade head
   ```

2. **Terminal A — start the FastAPI backend** (leave this running):

   ```bash
   cd user_management_api
   source .venv/bin/activate
   uvicorn app.asgi:app --reload --host 127.0.0.1 --port 8001
   ```

   - OpenAPI: `http://127.0.0.1:8001/docs`
   - The UI will call this base URL; default in the UI app is `http://localhost:8001` **only if** you do not set `BACKEND_URL`. To avoid ambiguity, set `BACKEND_URL` explicitly in step 3.

3. **Terminal B — start the Streamlit UI** and point it at the API with **`BACKEND_URL`**:

   ```bash
   cd user_management_ui
   python -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

   Edit `user_management_ui/.env` and set (matching Terminal A):

   ```env
   BACKEND_URL=http://127.0.0.1:8001
   ```

   Then run:

   ```bash
   streamlit run user_app.py --server.port 8502 --server.address 127.0.0.1
   ```

   - App: `http://127.0.0.1:8502`

4. **Sign in**: after `alembic upgrade head`, the migration seeds a default admin unless you override it with `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` — default is `admin@example.com` / `admin123` (see `user_management_api/README.md`).

**If login or API calls fail**, confirm `BACKEND_URL` is exactly the URL the Streamlit **server** can reach (same machine → `http://127.0.0.1:8001` or `http://localhost:8001` consistently). The UI never embeds the API; it always uses HTTP from the Streamlit process to the API.

## Posit Connect note (HTML UI vs Streamlit)

The backend originally shipped with a server-rendered HTML UI (cookie-based session via `Set-Cookie`).
When deployed to **Posit Connect**, that HTML UI proved unreliable because browsers would not persist the app’s login cookie in the Connect embedded context. We attempted standard mitigations (e.g. `SameSite=None; Secure`, legacy cookies), but cookie persistence still failed.

As a result, we recommend deploying the **Streamlit UI** (`user_management_ui/`) on Connect instead. Streamlit keeps the JWT in server-side session state and avoids browser cookie persistence issues.

## Environment

### Backend (`user_management_api/.env`)

- `DATABASE_URL`: e.g. `sqlite:///./app.db`
- `JWT_SECRET`: secret used to sign JWTs
- `JWT_EXPIRES_MINUTES`: default `60`
- `JWT_ALGORITHM`: default `HS256`

### User management UI (`user_management_ui/.env`, optional)

- `BACKEND_URL`: must match the API URL (e.g. `http://127.0.0.1:8001` when running locally as in the quickstart above)

## Run tests

Use a **repo root** virtualenv and install everything once:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-dev.txt
python -m pytest
```

If the venv already exists:

```bash
source .venv/bin/activate
python -m pytest
```

If you only want the backend + `fastapi_workbench` tests (no Streamlit deps), run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q user_management_api/tests fastapi_workbench/tests
```
 
