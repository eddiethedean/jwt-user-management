# Streamlit User App (Demo)

User-facing demo Streamlit app that logs in against the backend and demonstrates a password reset flow.

## Run locally

1) Ensure the backend is running.

```bash
cd backend
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
- To demonstrate “stay logged in”, the app also stores the JWT in a **signed cookie**.
  - Configure via `.env`:
    - `USER_COOKIE_NAME`
    - `USER_COOKIE_KEY` (set a strong random secret)
    - `USER_COOKIE_EXPIRY_DAYS`

## Password reset behavior

- “Forgot password” calls `POST /password/forgot` (always returns ok to avoid account enumeration).
- For a real reset, users click the link emailed by the backend (`/password/reset?token=...`).
- The app also includes a “Reset using token” demo that calls `POST /password/reset`.

