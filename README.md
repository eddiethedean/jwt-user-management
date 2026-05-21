# JWT User Management (bare-bones)

This repo contains:

- **`user_management_api/`** — FastAPI + SQLModel + Alembic backend with JWT auth (API-only).
- **`user_management_streamlit/`** — Streamlit UI (`BACKEND_URL`) plus optional legacy HTML UI (`html_app.py`, cookie auth).
- **`fluxlit_app/`** — Single-process [FluxLit](https://fluxlit.readthedocs.io/en/stable/) app: FastAPI mounted at **`/api`** plus Streamlit in one ASGI app.
- **`e2e/`** — Playwright browser tests.
- **`fastapi_workbench/`** — Helpers for Posit Workbench / RStudio Server path prefixes (used by the standalone API).

Package READMEs for deeper topics: [`user_management_api/README.md`](user_management_api/README.md), [`user_management_streamlit/README.md`](user_management_streamlit/README.md), [`fluxlit_app/README.md`](fluxlit_app/README.md), [`e2e/README.md`](e2e/README.md).

**First-time setup:** use [Setup from scratch](#setup-from-scratch) below for end-to-end local instructions. If you use a source ZIP instead of Git, unpack it and `cd` into the project folder; skip the `git clone` step.

---

## Setup from scratch

Follow **either** [Option A](#option-a-standalone-api--streamlit-two-processes) (split backend + UI) **or** [Option B](#option-b-fluxlit-single-process). You do not need both for a working demo.

### Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Git** | To clone this repository. |
| **Python 3.10+** | Required for `user_management_api` and `user_management_streamlit`. |
| **Python 3.11+** | Required for `fluxlit_app` only (Option B). |
| **Two terminal windows/tabs** | Option A runs the API and Streamlit separately. |

On Windows, use `\.venv\Scripts\activate` instead of `source .venv/bin/activate`.

### 1. Get the code

```bash
git clone <repository-url> jwt-user-management
cd jwt-user-management
```

Use your real clone URL in place of `<repository-url>`.

---

### Option A: Standalone API + Streamlit (two processes)

Use this path to run the same layout as production-style deployments: API on one host/port, Streamlit on another. Each component uses its **own** `.venv` inside its directory (so you activate the correct venv before each command).

#### Step A1 — Create the API virtual environment and install dependencies

```bash
cd user_management_api
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

#### Step A2 — Configure the API (`.env` and optional `config.py`)

```bash
cp .env.example .env
```

1. Edit **`user_management_api/.env`** and set **`JWT_SECRET`** (required in production; the example file includes a dev placeholder).
2. Non-sensitive tunables (cookie flags, SMTP port/TLS, directory timeouts, `BASE_PATH`, `PUBLIC_BASE_URL`, `UI_PUBLIC_BASE_URL`, JWT algorithm/lifetime, invite email domains, etc.) live only in **`user_management_api/config.py`**. Use **`.env`** for secrets and deployment endpoints: **`DATABASE_URL`**, **`JWT_SECRET`**, SMTP credentials, **`DIRECTORY_LOOKUP_URL`**, optional **`DIRECTORY_LOOKUP_CA_BUNDLE`**, and **`SEED_*`** if you customize seeding.

| Override (`.env`) | When you need it |
|---------------------|------------------|
| **`JWT_SECRET`** | Always set a strong value before production. |
| **`DATABASE_URL`** | If not using the default SQLite URL from `.env.example`. |
| **`DIRECTORY_LOOKUP_URL`** | When you enable the optional directory HTTP client. |

Leave the rest of `.env` commented unless you need SMTP or directory lookup ([optional features](#optional-directory-lookup-and-smtp)).

#### Step A3 — Create database tables and seed admin

Still inside `user_management_api/` with the venv activated:

```bash
alembic upgrade head
```

To migrate **both** the API and FluxLit databases in one step (from repo root): `./scripts/migrate_databases.sh`.

This applies migrations and creates a default admin user unless you set `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` in `.env`.

**Default admin (if you did not override seed env vars):**

- Email: **`admin@example.com`**
- Password: **`admin123`**

#### Step A4 — Start the API (keep this terminal open)

```bash
cd user_management_api
source .venv/bin/activate
uvicorn app.asgi:app --reload --host 127.0.0.1 --port 8001
```

- **OpenAPI docs:** `http://127.0.0.1:8001/docs`
- **Health check:** open `/docs` or call any documented route.

#### Step A5 — Create the Streamlit UI virtual environment and install dependencies

Open a **second** terminal:

```bash
cd user_management_streamlit
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

#### Step A6 — Point the UI at the API

```bash
cp .env.example .env
```

Edit **`user_management_streamlit/.env`** and set:

```env
BACKEND_URL=http://127.0.0.1:8001
```

Use the same host and port as Step A4. The Streamlit **server** must be able to reach this URL (not only your browser). Fallback pieces for local dev when `BACKEND_URL` is unset (`PORT`, `BASE_PATH`) and the default for **`DEBUG`** are defined in **`user_management_streamlit/config.py`**.

For **invite and password-reset emails** to open the Streamlit app directly, set **`UI_PUBLIC_BASE_URL`** in **`user_management_api/config.py`** to the public Streamlit origin (for example `http://127.0.0.1:8502`). The API then emails links of the form `.../?page=Accept+invite&token=...` and `.../?page=Reset+password&token=...`, which the UI reads on load. If you leave it empty, links keep the older API-style paths (`/invites/accept?token=...`, `/password/reset?token=...`).

#### Step A7 — Start the Streamlit app

```bash
cd user_management_streamlit
source .venv/bin/activate
streamlit run user_app.py --server.port 8502 --server.address 127.0.0.1
```

- **App URL:** `http://127.0.0.1:8502`

#### Step A8 — Sign in

1. Open `http://127.0.0.1:8502`.
2. Log in with the admin email and password from Step A3.

If login fails, see [Troubleshooting](#troubleshooting).

---

### Option B: FluxLit single process

One Python environment runs the gateway, Streamlit UI, and JSON API together (default bind **`127.0.0.1:8000`**).

#### Step B1 — Create virtual environment and install

```bash
cd fluxlit_app
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

Python **3.11+** is required for this package (see `fluxlit_app/README.md`).

#### Step B2 — Configure environment

```bash
cp .env.example .env
```

Edit **`fluxlit_app/.env`**: set **`DATABASE_URL`** and **`JWT_SECRET`** (see `.env.example`). Tunables for the bundled FastAPI app (`PUBLIC_BASE_URL`, `BASE_PATH`, JWT algorithm/lifetime, SMTP port/TLS, directory timeouts, invite domains) are only in **`fluxlit_app/config.py`**. FluxLit gateway variables remain the usual **`FLUXLIT_*`** names (see `.env.example` comments and `fluxlit_app/README.md`).

#### Step B3 — Migrate and run

From **`fluxlit_app/`** with the venv activated:

```bash
cd fluxlit_app
source .venv/bin/activate
alembic upgrade head
fluxlit dev
```

With default settings:

| What | URL |
|------|-----|
| Streamlit UI | `http://127.0.0.1:8000/` |
| OpenAPI | `http://127.0.0.1:8000/api/docs` |
| API (relative to app) | under **`/api/...`** |

Sign in with the same style of seeded admin as in the API package (see `fluxlit_app/README.md` seed section).

Alternative: `uvicorn main:app --reload --host 127.0.0.1 --port 8000` from `fluxlit_app/` — see `fluxlit_app/README.md`.

---

### Optional: directory lookup and SMTP

Both **`user_management_api`** and **`fluxlit_app`** can:

- Call an HTTP **directory** service (`GET` base URL + `?query=<email>`) to read **country** (and display fields) from LDAP-style JSON (`attributes.c` / `attributes.co`) when **accepting** an invite or refreshing an existing user—**not** to block creating invites or self-registration when the directory has no match.
- Restrict **invite and registration** addresses to specific **email domains** via **`INVITE_ALLOWED_EMAIL_DOMAINS`** in each package’s **`config.py`** (tuple of suffixes after `@`).
- Send **email** for invites, registration setup, and password reset when **`SMTP_HOST`** and **`SMTP_FROM_EMAIL`** are set.

**Setup outline:**

1. Copy the relevant package `.env.example` to `.env` (you should already have `.env` from the steps above).
2. Set **`DIRECTORY_LOOKUP_URL`** in `.env` to your lookup service base URL (not in `config.py` — deployment-specific).
3. Optional tuning such as **`DIRECTORY_LOOKUP_TIMEOUT_S`** and **`DIRECTORY_LOOKUP_REQUIRED`** is defined in each package’s **`config.py`**. **`DIRECTORY_LOOKUP_REQUIRED`** only affects whether directory HTTP failures can raise inside the low-level client—not whether invites are allowed.
4. Edit **`INVITE_ALLOWED_EMAIL_DOMAINS`** in **`config.py`** if you need domains beyond the defaults (**`socom.mil`** and **`soc.mil`**).
5. Set SMTP variables in `.env` as needed.

Full variable lists and behavior: [`user_management_api/README.md`](user_management_api/README.md) and [`fluxlit_app/README.md`](fluxlit_app/README.md).

---

### Run automated tests (repository root)

Use one virtualenv at the **repo root** so pytest can see all packages:

```bash
cd jwt-user-management
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-dev.txt
```

Run the full suite:

```bash
python -m pytest
```

**Backend and `fastapi_workbench` only** (lighter, avoids loading all Streamlit plugins):

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q user_management_api/tests fastapi_workbench/tests
```

**End-to-end browser tests** need Playwright browsers installed once:

```bash
playwright install
```

Then see [`e2e/README.md`](e2e/README.md) for how to run `e2e/` tests (from the repo root, with the same venv activated).

---

### Posit Connect and Workbench

- **Connect:** Prefer the **Streamlit** UI (`user_management_streamlit` or the FluxLit UI) over cookie-based HTML login; see the note in [`user_management_api/README.md`](user_management_api/README.md).
- **Workbench / path prefixes:** Standalone API: `user_management_api/run_workbench.py`. FluxLit: `fluxlit_app/run_workbench.py` and `fluxlit_app/README.md`.

---

### Troubleshooting

| Problem | What to check |
|---------|----------------|
| Streamlit cannot log in or “backend request failed” | **`BACKEND_URL`** must be exactly what the Streamlit **process** can call (e.g. `http://127.0.0.1:8001`). Mixing `localhost` vs `127.0.0.1` can matter in some setups; pick one and use it everywhere. |
| API exits or 500 on startup | **`JWT_SECRET`** must be non-empty in `user_management_api/.env`. |
| `alembic` errors | Run `alembic upgrade head` from **`user_management_api/`** or **`fluxlit_app/`** (respectively), with that package’s venv activated and `DATABASE_URL` pointing at a writable path. |
| UI rejects `BACKEND_URL` | `user_management_streamlit` blocks obviously unsafe URLs; use a normal `http://127.0.0.1:PORT` style URL for local dev. See [`user_management_streamlit/README.md`](user_management_streamlit/README.md). |
