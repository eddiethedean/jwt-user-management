# User management UI (Streamlit)

User-facing demo Streamlit app that logs in against the backend.

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
cd user_management_ui
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

## Environment (`user_management_ui/.env`)

- **`BACKEND_URL`**: full base URL of the FastAPI API (no trailing slash), e.g. `http://127.0.0.1:8001`. Required for real deployments; if unset, the app falls back to `http://localhost:${PORT:-8001}${BASE_PATH}` for local dev.
- **`DEBUG`**: set to `true` for sidebar diagnostics.

### Backend URL safety checks

The user app validates its backend base URL:

- It must be a full `http(s)://` URL and must not include credentials.
- It rejects targeting private / link-local / reserved IP ranges.
- For hostnames, it resolves A/AAAA records and rejects any private/link-local/etc resolution (hostnames like `localhost` are allowed).

## Run tests

```bash
cd user_management_ui
source .venv/bin/activate
pytest
```

