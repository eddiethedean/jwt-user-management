# Streamlit User App (Demo)

User-facing demo Streamlit app that logs in against the backend and demonstrates a password reset flow.

## Run locally

Prereqs: **Python 3.10+**.

1) Ensure the backend is running.

```bash
cd user_management_api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

2) Start the user demo app.

```bash
cd streamlit_user
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py --server.port 8502 --server.fileWatcherType none
```

Open `http://localhost:8502`.

## Authentication behavior

- **Login** calls `POST /auth/token` and stores the returned JWT in session state.
- This demo does not persist auth across browser refreshes; it’s intentionally minimal.

### Backend URL safety checks

The user app validates `BACKEND_URL`:

- It must be a full `http(s)://` URL and must not include credentials.
- It rejects targeting private / link-local / reserved IP ranges (hostnames like `localhost` are allowed).

## Password reset behavior

- “Forgot password” calls `POST /password/forgot` (always returns ok to avoid account enumeration).
- For a real reset, users click the link emailed by the backend (`/password/reset?token=...`).
- The app also includes a “Reset using token” demo that calls `POST /password/reset`.

## Run tests

```bash
cd streamlit_user
source .venv/bin/activate
pytest
```

