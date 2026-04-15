# Streamlit Admin App

Admin-only Streamlit UI for managing users and sending invites.

## Run locally

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

