# FluxLit JWT user management

**Full from-scratch setup:** see the repository root [`README.md`](../README.md#setup-from-scratch) (Option B).

Self-contained [FluxLit](https://fluxlit.readthedocs.io/en/stable/) application: **one ASGI process** with a bundled **FastAPI** app under [`app/`](app/) (JSON API on `/api`) and a **Streamlit** UI in [`ui/pages/`](ui/pages/). Optional **URL session** continuity uses a query parameter (default `fluxlit_sid`) plus server-side storage; gateway behavior is configured with [`fluxlit.toml`](fluxlit.toml) and `FLUXLIT_*` environment variables.

Database migrations live here as well ([`alembic/`](alembic/), [`alembic.ini`](alembic.ini)); run `alembic upgrade head` from **`fluxlit_app/`** after editing `.env`.

## Posit Connect / proxy

- The Streamlit UI keeps the JWT in **Streamlit session state**, which tends to behave better in embedded Connect / proxy contexts than the retired server-rendered HTML UI.
- Invite and password-reset links use FluxLit's native public URL helpers. Prefer **`FLUXLIT_PUBLIC_BASE_URL`** and keep it aligned with the URL users see in the browser.
- Behind a path prefix or reverse proxy, set **`FLUXLIT_ROOT_PATH`** and typically **`FLUXLIT_TRUST_PROXY=1`**. FluxLit 0.8.1 handles app/API/docs URLs and Workbench mode directly.

## Run locally

Prereqs: **Python 3.11+** (see [`requirements.txt`](requirements.txt)).

```bash
cd fluxlit_app
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env (at least DATABASE_URL, JWT_SECRET); tune PUBLIC_BASE_URL in config.py
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

Use FluxLit's native Workbench/Connect mode. [`run_workbench.py`](run_workbench.py) is a small compatibility launcher around the same native runtime:

```bash
cd fluxlit_app
source .venv/bin/activate
python run_workbench.py
```

For connection and proxy debugging:

```bash
python run_workbench.py --debug --no-browser
```

Debug mode turns on:

- `DEBUG=1` for the Streamlit sidebar debug panel, including UI-side API-base information;
- `LOG_LEVEL=debug` for Uvicorn;
- `FLUXLIT_DEBUG=1` for FluxLit gateway diagnostics, request logging, and `GET /__fluxlit/debug`;
- `FLUXLIT_TRACE_LOGGING=1` for the optional local trace hook.

The launcher:

- runs Alembic migrations by default (`RUN_MIGRATIONS=0` disables this);
- maps legacy `BASE_PATH` to `FLUXLIT_ROOT_PATH`;
- enables `FLUXLIT_TRUST_PROXY=1` by default;
- starts `main:app` with FluxLit's native `workbench_mode=True`.

You can also call FluxLit directly:

```bash
cd fluxlit_app
source .venv/bin/activate
fluxlit workbench --debug
```

For local prefix testing without a real Workbench session:

```bash
cd fluxlit_app
source .venv/bin/activate
BASE_PATH=/workbench \
FLUXLIT_ROOT_PATH=/workbench \
FLUXLIT_PUBLIC_BASE_URL=http://127.0.0.1:8768/workbench \
PORT=8768 \
python -c 'from run_workbench import start_app; start_app(open_with_browser=False)'
```

Then open `http://127.0.0.1:8768/workbench/`; API docs are at `http://127.0.0.1:8768/workbench/api/docs`.

Keep **`FLUXLIT_PUBLIC_BASE_URL`** consistent with the external app URL used for invite and reset links. `PUBLIC_BASE_URL` remains supported as a legacy fallback by FluxLit 0.8.1, but new deployments should prefer the namespaced setting.

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
| `DATABASE_URL` | Set in `.env` (see `.env.example`). |
| `JWT_SECRET` | Set in `.env`. |
| `JWT_ALGORITHM` / `JWT_EXPIRES_MINUTES` | Edit **`config.py`** (defaults: HS256, 60 minutes). |
| `PUBLIC_BASE_URL` | Edit **`config.py`** (default matches local `fluxlit dev`). |

Tunables such as **`BASE_PATH`**, **`INVITE_ALLOWED_EMAIL_DOMAINS`**, SMTP port/TLS, and directory timeouts live only in **`config.py`** beside `app/`. **`.env`** must not duplicate those keys.

### Optional: directory (LDAP) lookup

This matches the standalone **`user_management_api`** behavior (see that package’s README for the full contract). Summary:

1. Set **`DIRECTORY_LOOKUP_URL`** to the directory HTTP **base URL**. The app calls:

   `GET <DIRECTORY_LOOKUP_URL>?query=<email>`

2. Expect JSON with **`attributes`**: **`mail`** or **`userPrincipalName`** for identity; optional **`displayName`** / **`cn`**; optional country from **`c`** or **`co`** (values like `C=US` are stored as `US`).

3. **`DIRECTORY_LOOKUP_REQUIRED`**: when `true`, directory transport/parse failures can cause **`lookup_email`** to raise at the HTTP client layer. **Invites and self-registration are not blocked** when the directory has no match; directory data is used to set **`user.country`** when a user **accepts** an invite when a record exists.

4. Tune **`DIRECTORY_LOOKUP_TIMEOUT_S`**, **`DIRECTORY_LOOKUP_VERIFY_SSL`** in **`config.py`**. Set **`DIRECTORY_LOOKUP_CA_BUNDLE`** in **`.env`** when you need a custom CA file path.

5. **Invite / registration domains:** edit the **`INVITE_ALLOWED_EMAIL_DOMAINS`** tuple in **`config.py`** (defaults **`socom.mil`**, **`soc.mil`**).

The Streamlit **Admin** flow calls **`POST /api/invites/lookup`** for a **preview** of directory email, name, and country when the service responds; failures return empty fields without blocking **`POST /api/invites`**.

JSON routes live under **`/api`** (for example **`POST /api/invites/lookup`**).

### Optional: SMTP (invites, self-registration, password reset)

Configure **`SMTP_HOST`**, **`SMTP_FROM_EMAIL`**, and related variables from [`.env.example`](.env.example) so the API can send email. If SMTP is unset, token creation and invite URLs still work; sending is skipped.

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
| [`run_workbench.py`](run_workbench.py) | Posit Workbench-friendly launcher using FluxLit's native `workbench_mode`. |
| [`app/`](app/) | Bundled FastAPI application (models, routes, config). |
| [`alembic/`](alembic/) | SQL migrations for `app`. |
| [`api_backend.py`](api_backend.py) | Mounts routers and `GET /__meta`. |
| [`paths.py`](paths.py) | Puts this directory on `sys.path` and loads `.env`. |
| [`fluxlit_settings.py`](fluxlit_settings.py) | Default `FluxlitSettings`. |
| [`fluxlit_trace.py`](fluxlit_trace.py) | Optional `FLUXLIT_TRACE_LOGGING` hook. |
| [`ui/pages/jwt_users_page.py`](ui/pages/jwt_users_page.py) | FluxLit `register(app)` entry. |
| [`ui/pages/um_*.py`](ui/pages/) | Streamlit screen modules. |
| [`ui/http.py`](ui/http.py) | HTTP helpers for the UI. |

## Documentation

- [FluxLit quickstart](https://fluxlit.readthedocs.io/en/stable/quickstart.html)
- [FluxLit configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html)
