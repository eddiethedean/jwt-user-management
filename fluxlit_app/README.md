# FluxLit app (user management UI + API)

This directory is a [FluxLit](https://fluxlit.readthedocs.io/en/stable/) application: **one ASGI process** that serves the same **FastAPI** app as [`user_management_api`](../user_management_api) (mounted under `/api`) and a **Streamlit** UI (registered from [`ui/pages/`](ui/pages/)). Behavior matches the standalone [`streamlit_user`](../streamlit_user) app, with FluxLit handling routing, optional URL-session continuity (`fluxlit_sid`), and gateway settings via `fluxlit.toml` and `FLUXLIT_*` env vars.

For **API-only** or deeper API docs, see [`user_management_api/README.md`](../user_management_api/README.md).

## Posit Connect / proxy note

- The Streamlit UI stores the JWT in **Streamlit session state** (not HTML form cookies), which is usually easier behind embedded Connect / proxy setups than a cookie-only HTML UI.
- Invite and password-reset links use **`PUBLIC_BASE_URL`** (and FluxLit’s **`FLUXLIT_PUBLIC_BASE_URL`** when you set it). Point them at the **browser-visible** origin (scheme + host + optional gateway prefix).
- Behind Workbench or another path prefix, set **`FLUXLIT_ROOT_PATH`** (and/or follow FluxLit’s proxy docs: **`FLUXLIT_TRUST_PROXY`**). Path-aware helpers come from [`fastapi_workbench`](../fastapi_workbench/) (same stack as the API’s `GET /__meta`).

## Run locally

Prereqs: **Python 3.11+** (matches the pinned `fluxlit` stack in [`requirements.txt`](requirements.txt)).

```bash
cd fluxlit_app
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: DATABASE_URL, JWT_*, PUBLIC_BASE_URL (see Environment below)
(cd ../user_management_api && alembic upgrade head)
fluxlit dev
```

With default [`fluxlit.toml`](fluxlit.toml) bind (`127.0.0.1:8000`):

- **Streamlit UI (root):** `http://127.0.0.1:8000/`
- **OpenAPI docs:** `http://127.0.0.1:8000/api/docs`
- **API JSON root (health-style):** `http://127.0.0.1:8000/api/`

`fluxlit dev` reads **`fluxlit.toml`** from the current directory. Run it from **`fluxlit_app/`** so `.env` and the project file resolve as expected.

### Run with Uvicorn (reload)

```bash
cd fluxlit_app
source .venv/bin/activate
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Legacy alias (same `app` object): `uvicorn fluxlit_gateway:app --reload --host 127.0.0.1 --port 8000`.

### Import / `fluxlit doctor` issues

If Python cannot import **`main`** (e.g. wrong working directory), put this directory on **`PYTHONPATH`**:

```bash
export PYTHONPATH="$(pwd)"   # from inside fluxlit_app
fluxlit doctor
```

## Run on Workbench (behind a proxy prefix)

Path and external URL behavior mirror the API project: see **Run on Workbench** in [`user_management_api/README.md`](../user_management_api/README.md) for `BASE_PATH`, `PUBLIC_BASE_URL`, and the `run_workbench.py` helper.

For **FluxLit** specifically:

- Set **`FLUXLIT_ROOT_PATH`** to the browser-visible prefix (FluxLit wires Streamlit `baseUrlPath` and gateway routing).
- Set **`FLUXLIT_TRUST_PROXY=1`** when TLS and host are forwarded via `X-Forwarded-*`.
- Keep **`PUBLIC_BASE_URL`** (backend) and **`FLUXLIT_PUBLIC_BASE_URL`** (gateway) aligned with what users type in the browser.

## JSON API (under `/api`)

Same contract as `user_management_api`, but paths are prefixed with **`/api`** when using this gateway:

| Action | Method and path |
|--------|------------------|
| JWT token | `POST /api/auth/token` (form: `username` = email, `password`) |
| Current user | `GET /api/users/me` (Bearer) |
| List users | `GET /api/users` (Bearer) |
| Create invite (admin) | `POST /api/invites` (Bearer; JSON `{"email": "..."}`) |
| Accept invite | `POST /api/invites/accept` (JSON `token`, `password`, …) |

Example (default local port **8000**):

```bash
TOKEN="$(curl -sS -X POST http://127.0.0.1:8000/api/auth/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin@example.com&password=admin123' \
  | python -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')"

curl -sS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/users/me
```

## Environment

Dotenv files load in this order (later overrides earlier):

1. [`../user_management_api/.env`](../user_management_api/.env) — shared backend (`DATABASE_URL`, `JWT_*`, email, directory lookup, …).
2. [`./.env`](.env) — FluxLit app overrides (copy from [`.env.example`](.env.example)).

### Backend (same semantics as `user_management_api`)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | e.g. `sqlite:///../user_management_api/app.db` |
| `PUBLIC_BASE_URL` | External origin for invite/reset links (`http://127.0.0.1:8000` locally) |
| `JWT_SECRET` | Signs JWTs |
| `JWT_EXPIRES_MINUTES` | Default `60` |
| `JWT_ALGORITHM` | Default `HS256` |

Optional Workbench / proxy vars (`BASE_PATH`, etc.) are documented in **`user_management_api/.env.example`**.

### FluxLit gateway (`FLUXLIT_*`)

See [`.env.example`](.env.example) for the full list. Common ones:

| Variable | Purpose |
|----------|---------|
| `FLUXLIT_PUBLIC_BASE_URL` | Public origin for OAuth redirects and external URL hints |
| `FLUXLIT_ROOT_PATH` | Subpath when mounted behind a reverse proxy |
| `FLUXLIT_TRUST_PROXY` | Trust `X-Forwarded-*` from Uvicorn |
| `FLUXLIT_ENABLE_SECURITY_HEADERS` | Security headers middleware |
| `FLUXLIT_URL_SESSION_QUERY_PARAM` | Query key for URL-bound session (default `fluxlit_sid`) |
| `FLUXLIT_DISABLE_URL_SESSION` | Set to disable the URL-session bridge in the UI |

Details: [FluxLit configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html) and [`fluxlit.toml`](fluxlit.toml).

### Seed an initial admin user (optional)

On `alembic upgrade head` in **`user_management_api`**, a default admin is created if missing (same as the API README):

- Email: `admin@example.com`
- Password: `admin123`

Override with **`SEED_ADMIN_EMAIL`** and **`SEED_ADMIN_PASSWORD`** in `user_management_api/.env`.

## Run tests

From the **repository root** (uses root [`pytest.ini`](../pytest.ini) `pythonpath` and `addopts`):

```bash
pip install -r fluxlit_app/requirements.txt
python -m pytest fluxlit_app/tests -q
```

If a **globally installed** pytest plugin still breaks collection, try:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest fluxlit_app/tests -q
```

## Project layout

| Path | Role |
|------|------|
| [`main.py`](main.py) | ASGI entry: `FluxLit`, `import_target="main:app"`, routes, `discover_pages`. |
| [`fluxlit_gateway.py`](fluxlit_gateway.py) | Legacy `app` re-export (`fluxlit_gateway:app`). |
| [`fluxlit_settings.py`](fluxlit_settings.py) | Default `FluxlitSettings`; overridden by `FLUXLIT_*`. |
| [`fluxlit_trace.py`](fluxlit_trace.py) | Optional `FLUXLIT_TRACE_LOGGING` → `set_trace_hook`. |
| [`api_backend.py`](api_backend.py) | Mounts API routers, `GET /__meta`, cookie-debug middleware. |
| [`cookie_debug_middleware.py`](cookie_debug_middleware.py) | Cookie debug middleware (parity with API app). |
| [`paths.py`](paths.py) | `sys.path` + dotenv bootstrap for `user_management_api`. |
| [`ui/pages/user_management.py`](ui/pages/user_management.py) | FluxLit `register(app)`; URL session + delegates to `um_*` screens. |
| [`ui/pages/um_*.py`](ui/pages/) | Public vs authenticated Streamlit UI chunks. |
| [`ui/http.py`](ui/http.py) | `response_ok`, `fluxlit_api_client_kwargs`, `safe_json`, … |

## Dependencies

[`requirements.txt`](requirements.txt) pins **`fluxlit[auth]`** and lists the same direct packages as [`user_management_api/requirements.txt`](../user_management_api/requirements.txt). When you change the API stack, keep those two requirement files aligned.

## Documentation

- [FluxLit quickstart](https://fluxlit.readthedocs.io/en/stable/quickstart.html)
- [FluxLit configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html)
