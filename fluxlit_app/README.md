# FluxLit user management app

This directory is a [FluxLit](https://fluxlit.readthedocs.io/en/stable/) application: a single ASGI process that serves the **FastAPI** API from [`user_management_api`](../user_management_api) and a **Streamlit** UI discovered from [`ui/pages/`](ui/pages/). It mirrors the behavior of the standalone `streamlit_user` app while following FluxLit’s layout and configuration model.

## Requirements

- Python 3.11+ (aligned with the rest of this repo).
- Dependencies from [`requirements.txt`](requirements.txt): pinned `fluxlit[auth]` plus the same direct packages as [`user_management_api/requirements.txt`](../user_management_api/requirements.txt) (keep the two files aligned when the API stack changes).
- A configured database and migrations for `user_management_api` (same `DATABASE_URL` semantics as the API).

## Setup

1. Create or reuse a virtual environment (the repo often uses `user_management_api/.venv`; install this app’s requirements there or in a dedicated venv).

   ```bash
   pip install -r requirements.txt
   ```

2. Copy environment defaults and adjust paths and secrets.

   ```bash
   cp .env.example .env
   ```

   Keep `DATABASE_URL`, `JWT_*`, and `PUBLIC_BASE_URL` consistent with [`user_management_api`](../user_management_api). Optional **`FLUXLIT_*`** variables are documented in [`.env.example`](.env.example); see the FluxLit [configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html) guide.

3. Apply database migrations from the API project.

   ```bash
   (cd ../user_management_api && alembic upgrade head)
   ```

## Run locally

Run commands **from this directory** (`fluxlit_app/`) so `fluxlit.toml` and `.env` resolve correctly. FluxLit must be able to import the module `fluxlit_gateway` (this folder must be on `PYTHONPATH` if you start Uvicorn from elsewhere).

```bash
fluxlit dev
```

Equivalent ASGI entry (after `cd fluxlit_app` and the same `PYTHONPATH` rule):

```bash
uvicorn fluxlit_gateway:app --host 127.0.0.1 --port 8000
```

Defaults for host, port, and log level also live in [`fluxlit.toml`](fluxlit.toml). If `fluxlit doctor` or imports fail with “cannot import `fluxlit_gateway`”, set `PYTHONPATH` to the absolute path of this directory (see comments in `fluxlit.toml` and `.env.example`).

## Project layout (short)

| Path | Role |
|------|------|
| [`fluxlit_gateway.py`](fluxlit_gateway.py) | ASGI entry: `FluxLit`, `discover_pages`, route installation. |
| [`fluxlit_settings.py`](fluxlit_settings.py) | `FluxlitSettings` defaults; env `FLUXLIT_*` overrides. |
| [`fluxlit_trace.py`](fluxlit_trace.py) | Optional `FLUXLIT_TRACE_LOGGING` → `set_trace_hook`. |
| [`api_backend.py`](api_backend.py) | Mounts API routers, `__meta`, and cookie-debug middleware. |
| [`cookie_debug_middleware.py`](cookie_debug_middleware.py) | Cookie debug middleware (parity with standalone API app). |
| [`paths.py`](paths.py) | `sys.path` and dotenv bootstrap for `user_management_api`. |
| [`ui/pages/user_management.py`](ui/pages/user_management.py) | FluxLit `register(app)` entry; wires URL session and delegates to screen modules. |
| [`ui/pages/um_*.py`](ui/pages/) | Helpers and split public vs authenticated Streamlit UI. |
| [`ui/http.py`](ui/http.py) | Shared HTTP helpers (`response_ok`, `fluxlit_api_client_kwargs`, …). |

## Tests

Automated tests live in [`tests/`](tests/). From the **repository root**:

```bash
python -m pytest fluxlit_app/tests
```

Use an environment where `fluxlit` and `user_management_api` dependencies are installed (for example after `pip install -r fluxlit_app/requirements.txt` in your venv). The root [`pytest.ini`](../pytest.ini) sets `pythonpath` and disables a conflicting global pytest plugin where needed.

## Documentation

- [FluxLit quickstart](https://fluxlit.readthedocs.io/en/stable/quickstart.html)
- [FluxLit configuration](https://fluxlit.readthedocs.io/en/stable/configuration.html) (`fluxlit.toml` + `FLUXLIT_*`)
