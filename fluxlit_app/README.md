# FluxLit JWT user management

Self-contained [FluxLit](https://fluxlit.readthedocs.io/en/stable/) application: **one ASGI process** with a bundled **FastAPI** app under [`app/`](app/) (JSON API on `/api`) and a **Streamlit** UI in [`ui/pages/`](ui/pages/). Optional **URL session** continuity uses a query parameter (default `fluxlit_sid`) plus server-side storage; gateway behavior is configured with [`fluxlit.toml`](fluxlit.toml) and `FLUXLIT_*` environment variables.

Database migrations live here as well ([`alembic/`](alembic/), [`alembic.ini`](alembic.ini)); run `alembic upgrade head` from **`fluxlit_app/`** after editing `.env`.

## Posit Connect / proxy

- The Streamlit UI keeps the JWT in **Streamlit session state**, which tends to behave better in embedded Connect / proxy contexts than cookie-only HTML UIs.
- Invite and password-reset links use **`PUBLIC_BASE_URL`**. Align it (and **`FLUXLIT_PUBLIC_BASE_URL`** when set) with the URL users see in the browser.
- Behind a path prefix or reverse proxy, set **`FLUXLIT_ROOT_PATH`** and typically **`FLUXLIT_TRUST_PROXY=1`**. Path-aware URL helpers use **`fastapi_workbench`** (add the repo’s `fastapi_workbench/src` directory to `PYTHONPATH` when it is not already installed as a package).

## Run locally

Prereqs: **Python 3.11+** (see [`requirements.txt`](requirements.txt)).

```bash
cd fluxlit_app
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env (at least DATABASE_URL, JWT_SECRET, PUBLIC_BASE_URL)
alembic upgrade head
fluxlit dev
```

With default [`fluxlit.toml`](fluxlit.toml) bind (`127.0.0.1:8000`):

- **Streamlit UI:** `http://127.0.0.1:8000/`
- **OpenAPI docs:** `http://127.0.0.1:8000/api/docs`
- **API JSON root:** `http://127.0.0.1:8000/api/`

Run **`fluxlit dev`** from **`fluxlit_app/`** so `fluxlit.toml` and `.env` resolve correctly.

### Run with Uvicorn (reload)

```bash
cd fluxlit_app
source .venv/bin/activate
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Legacy alias: `uvicorn fluxlit_gateway:app ...` (same `app` object).

### Import / `fluxlit doctor`

If Python cannot import **`main`**, export this directory on **`PYTHONPATH`**:

```bash
export PYTHONPATH="$(pwd)"   # from inside fluxlit_app
fluxlit doctor
```

## Run behind Workbench (path prefix)

- Set **`FLUXLIT_ROOT_PATH`** to the browser-visible prefix and enable **`FLUXLIT_TRUST_PROXY`** when the proxy terminates TLS and forwards `X-Forwarded-*`.
- Keep **`PUBLIC_BASE_URL`** consistent with the external origin used for invite and reset links.
- Workbench-style **`GET /__meta`** behavior uses `fastapi_workbench` (same headers as other apps in this repo that use that helper).

## JSON API (mounted at `/api`)

| Action | Method and path |
|--------|------------------|
| JWT token | `POST /api/auth/token` (form: `username` = email, `password`) |
| Current user | `GET /api/users/me` (Bearer) |
| List users | `GET /api/users` (Bearer) |
| Create invite (admin) | `POST /api/invites` (Bearer; JSON `{"email": "..."}`) |
| Accept invite | `POST /api/invites/accept` (JSON `token`, `password`, …) |

Example (port **8000**):

```bash
TOKEN="$(curl -sS -X POST http://127.0.0.1:8000/api/auth/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin@example.com&password=admin123' \
  | python -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')"

curl -sS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/users/me
```

## Environment

[`load_dotenv_files()`](paths.py) loads **`fluxlit_app/.env`** (create from [`.env.example`](.env.example)).

### Core variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy URL (default in `.env.example`: `sqlite:///./app.db` beside this tree) |
| `PUBLIC_BASE_URL` | External origin for invite/reset links |
| `JWT_SECRET` | Signs JWTs |
| `JWT_EXPIRES_MINUTES` | Default `60` |
| `JWT_ALGORITHM` | Default `HS256` |

Optional features (directory lookup, SMTP, cookie debug, etc.) are driven by the same settings as the bundled FastAPI [`app/core/config.py`](app/core/config.py).

### FluxLit gateway (`FLUXLIT_*`)

See [`.env.example`](.env.example) and the FluxLit [configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html) guide. Common keys include `FLUXLIT_PUBLIC_BASE_URL`, `FLUXLIT_ROOT_PATH`, `FLUXLIT_TRUST_PROXY`, `FLUXLIT_ENABLE_SECURITY_HEADERS`, and `FLUXLIT_URL_SESSION_QUERY_PARAM`.

### Seed admin (optional)

After **`alembic upgrade head`**, a default admin exists if migrations created one:

- Email: `admin@example.com`
- Password: `admin123`

Override with **`SEED_ADMIN_EMAIL`** and **`SEED_ADMIN_PASSWORD`** in `.env`.

## Run tests

From the **repository root** (see root [`pytest.ini`](../pytest.ini)):

```bash
pip install -r fluxlit_app/requirements.txt
python -m pytest fluxlit_app/tests -q
```

If a global pytest plugin interferes:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest fluxlit_app/tests -q
```

## Project layout

| Path | Role |
|------|------|
| [`main.py`](main.py) | ASGI entry: `FluxLit`, `import_target="main:app"`, routes, `discover_pages`. |
| [`fluxlit_gateway.py`](fluxlit_gateway.py) | Legacy `app` re-export. |
| [`app/`](app/) | Bundled FastAPI application (models, routes, config). |
| [`alembic/`](alembic/) | SQL migrations for `app`. |
| [`api_backend.py`](api_backend.py) | Mounts routers, `GET /__meta`, cookie-debug middleware. |
| [`cookie_debug_middleware.py`](cookie_debug_middleware.py) | Cookie debug middleware. |
| [`paths.py`](paths.py) | Puts this directory on `sys.path` and loads `.env`. |
| [`fluxlit_settings.py`](fluxlit_settings.py) | Default `FluxlitSettings`. |
| [`fluxlit_trace.py`](fluxlit_trace.py) | Optional `FLUXLIT_TRACE_LOGGING` hook. |
| [`ui/pages/jwt_users_page.py`](ui/pages/jwt_users_page.py) | FluxLit `register(app)` entry. |
| [`ui/pages/um_*.py`](ui/pages/) | Streamlit screen modules. |
| [`ui/http.py`](ui/http.py) | HTTP helpers for the UI. |

## Documentation

- [FluxLit quickstart](https://fluxlit.readthedocs.io/en/stable/quickstart.html)
- [FluxLit configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html)
