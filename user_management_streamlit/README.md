# User management UI (Streamlit)

Optional **Streamlit** demo that talks to the JSON API over HTTP (`BACKEND_URL`). The canonical browser UI for this repo is the **built-in HTML UI** served from **`user_management_api`** (see that package’s README).

**Full from-scratch setup:** see the repository root [`README.md`](../README.md#setup-from-scratch) (Option A).

## Run locally

Prereqs: **Python 3.10+**.

1) Start the API (HTML UI or API-only per **`user_management_api/config.py`**):

```bash
cd user_management_api
source .venv/bin/activate
uvicorn app.asgi:app --reload --port 8001
```

2) Start Streamlit with **`BACKEND_URL`** pointing at the API:

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

## Authentication behavior

- **Login** calls `POST /auth/token` and stores the returned JWT in session state.
- This demo does not persist auth across browser refreshes; it’s intentionally minimal.

## Environment (`user_management_streamlit/.env` and `config.py`)

- **`BACKEND_URL`**: full base URL of the FastAPI API (no trailing slash), e.g. `http://127.0.0.1:8001`. Required for real deployments; if unset, the app falls back to `http://localhost:${PORT}${BASE_PATH}` using defaults from **`config.py`** in this directory (`DEFAULT_BACKEND_PORT`, `DEFAULT_BACKEND_BASE_PATH`).

- **`DEBUG`**: set to `true` / `1` for sidebar diagnostics. If unset, the default comes from **`config.py`** (`DEBUG_DEFAULT`).

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
