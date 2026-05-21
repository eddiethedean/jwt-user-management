# User management UI (Streamlit + optional HTML)

**Streamlit** (`user_app.py`) is the primary UI: it talks to the JSON API over HTTP.

**Legacy HTML** (`html_app.py`) is also available in this package: cookie-auth,
server-rendered pages under `web/templates/` (restored from the API archive).

**Full from-scratch setup (clone, two venvs, `BACKEND_URL`, ports):** see the repository root [`README.md`](../README.md#setup-from-scratch) (Option A).

## Run locally

Prereqs: **Python 3.10+**.

1) Ensure the backend is running (separate terminal).

```bash
cd user_management_api
source .venv/bin/activate
uvicorn app.asgi:app --reload --port 8001
```

2) Start the user demo app with **`BACKEND_URL`** set to that API (copy `.env.example` to `.env` or export in the shell).

```bash
cd user_management_streamlit
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: BACKEND_URL=http://127.0.0.1:8001
streamlit run user_app.py --server.port 8502 --server.fileWatcherType none
```

Open `http://localhost:8502`.

## Legacy HTML UI (cookie auth)

Uses the same database and settings as `user_management_api` (run migrations there first).

```bash
cd user_management_streamlit
source .venv/bin/activate   # or repo root .venv with API + html deps
pip install -r requirements-html.txt
cp .env.example .env        # optional; also reads ../user_management_api/.env
python run_html.py
```

Open `http://127.0.0.1:8503/` (default). Pages: `/login`, `/register`, `/users`, `/admin`, invite/reset links, etc. Static assets: `/static/...`. See [`web/README.md`](web/README.md).

## Authentication behavior

- **Login** calls `POST /auth/token` and stores the returned JWT in session state.
- This demo does not persist auth across browser refreshes; it’s intentionally minimal.

## Environment (`user_management_streamlit/.env` and `config.py`)

- **`BACKEND_URL`**: full base URL of the FastAPI API (no trailing slash), e.g. `http://127.0.0.1:8001`. Required for real deployments; if unset, the app falls back to `http://localhost:${PORT}${BASE_PATH}` using defaults from **`config.py`** in this directory (`DEFAULT_BACKEND_PORT`, `DEFAULT_BACKEND_BASE_PATH`).

- **`DEBUG`**: set to `true` / `1` for sidebar diagnostics. If unset, the default comes from **`config.py`** (`DEBUG_DEFAULT`).

### Emailed deep links (Option A)

When the API’s **`UI_PUBLIC_BASE_URL`** (set in **`user_management_api/config.py`**) points at this Streamlit app (same origin users open in the browser), opening a URL with **`?page=Accept+invite&token=...`** or **`?page=Reset+password&token=...`** pre-fills the invite or reset flow.

### Backend URL safety checks

The user app validates its backend base URL:

- It must be a full `http(s)://` URL and must not include credentials.
- It rejects targeting private / link-local / reserved IP ranges.
- For hostnames, it resolves A/AAAA records and rejects any private/link-local/etc resolution (hostnames like `localhost` are allowed).

## Run tests

```bash
cd user_management_streamlit
source .venv/bin/activate
pytest
```

