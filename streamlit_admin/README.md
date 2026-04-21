# Streamlit Admin App

Admin-only Streamlit UI for managing users and sending invites.

## Run locally

Prereqs: **Python 3.10+**.

1) Ensure the backend is running.

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

2) Start the admin app.

```bash
cd streamlit_admin
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp config.example.yaml config.yaml
streamlit run app.py --server.port 8501 --server.fileWatcherType none
```

Open `http://localhost:8501`.

## Login credentials

Streamlit-Authenticator uses `streamlit_admin/config.yaml`.

- **Username**: the key under `credentials.usernames.*` (e.g. `admin`)
- **Password**: `credentials.usernames.<username>.password`

`streamlit_admin/config.yaml` is intentionally **gitignored**. Copy from `config.example.yaml` and set a real password.

## Backend integration

The admin app calls the backend using `X-Admin-Api-Key`.

Set in `streamlit_admin/.env`:
- `BACKEND_URL`
- `BACKEND_ADMIN_API_KEY` (must match backend `ADMIN_API_KEY`)

### Backend URL safety checks

The admin app validates `BACKEND_URL` to reduce SSRF-style footguns:

- For non-local backends, if `BACKEND_ADMIN_API_KEY` is set, `BACKEND_URL` must use `https://`.
- It rejects URLs containing credentials (e.g. `https://user:pass@host`).
- It rejects targeting private / link-local / reserved IP ranges.

### Test mode

For automated tests only, you can bypass Streamlit-Authenticator by setting:

- `STREAMLIT_TEST_MODE=1`
- `BACKEND_URL=http://testserver`

## Run tests

```bash
cd streamlit_admin
source .venv/bin/activate
pytest
```

