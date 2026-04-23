# Admin UI (Streamlit, served by backend)

Admin-only Streamlit UI for managing users and sending invites. The FastAPI backend runs this Streamlit app as an internal subprocess and serves it at `/admin/`.

## Run locally

Prereqs: **Python 3.10+**.

1) Start the backend (it will also start the admin UI subprocess).

```bash
cd user_management_api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Open `http://127.0.0.1:8000/admin/`.

## Login credentials

- Admin signs in via backend `POST /auth/token` and keeps the JWT in Streamlit session state (no cookie persistence).

## Backend integration

The admin app calls the backend using `X-Admin-Api-Key`.

Set in `user_management_api/admin_ui/.env` (optional for local dev; the backend also sets `BACKEND_URL` automatically when spawning the subprocess):
- `BACKEND_URL`
- `BACKEND_ADMIN_API_KEY` (must match backend `ADMIN_API_KEY`)

## Proxy auth (`/admin/*`)

The backend can optionally require an **admin JWT** for all `/admin/*` requests (HTTP + websocket):

- Set `ADMIN_UI_REQUIRE_JWT=1` in `user_management_api/.env`.

When enabled, you must have a valid admin session to access `/admin/`.

### Backend URL safety checks

The admin app validates `BACKEND_URL` to reduce SSRF-style footguns:

- For non-local backends, if `BACKEND_ADMIN_API_KEY` is set, `BACKEND_URL` must use `https://`.
- It rejects URLs containing credentials (e.g. `https://user:pass@host`).
- It rejects targeting private / link-local / reserved IP ranges.
- For hostnames, it resolves A/AAAA records and rejects any private/link-local/etc resolution.

### Test mode

For automated tests only, you can bypass Streamlit-Authenticator by setting:

- `STREAMLIT_TEST_MODE=1`
- `BACKEND_URL=http://testserver`

## Run tests

```bash
cd user_management_api/admin_ui
source .venv/bin/activate
pytest
```

