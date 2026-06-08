# User guide: `user_management_api`

How to **run**, **use**, and **deploy** the FastAPI backend and its built-in HTML UI.

| Doc | When to read |
|-----|----------------|
| [`README.md`](README.md) | Quickstart, API summary, tests |
| [`CONFIG.md`](CONFIG.md) | All settings (`config.py` + `.env`) |
| [`HTML_UI.md`](HTML_UI.md) | Pages, nav, branding |

---

## What this service provides

- **JWT API** — bearer tokens via `POST /auth/token`
- **HTML UI** — login, account, admin (same process as the API)
- **Invites** — admins invite users; accept via link or API
- **Self-registration** — optional (`SELF_REGISTRATION_ENABLED` in `config.py`)
- **Password reset** — forgot/reset email flow
- **Configurable roles** — multi-role assignment on admin edit user (`USER_ROLES` / `ADMIN_ROLES`)
- **Directory enrichment** — optional HTTP lookup for email/country on invite accept

**Alternate UI:** Streamlit in [`../user_management_streamlit/`](../user_management_streamlit/) with `BACKEND_URL` set to this API.

---

## Quickstart

```bash
cd user_management_api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
JWT_ALLOW_WEAK_SECRET=1 uvicorn app.asgi:app --reload --host 127.0.0.1 --port 8001
```

Open http://127.0.0.1:8001/login or http://127.0.0.1:8001/docs .

---

## Using the HTML UI

### Guests

- **Sign in** — `/login`
- **Register** — `/register` when `SELF_REGISTRATION_ENABLED` is `True` (sends setup email; requires SMTP)
- **Accept invite** — link from email → `/invites/accept?token=...`
- **Reset password** — `/password/reset?token=...` or forgot-password form on login page

### Non-admin users

- After login → **`/account`** (profile + password)
- Nav: **Account** only

### Admins

- After login → **`/admin`** (user list, invites)
- Edit user → `/admin/users/{id}` (roles, active flag, delete)
- Nav: **Admin**, **Account**
- Cannot change own admin/active status or delete self

### Root `/`

- Signed-in → `/admin` or `/account` by role  
- Guest → `/login`

---

## Configuration

**Do not duplicate settings.** Use two files:

1. **`config.py`** — committed tunables (see [`CONFIG.md`](CONFIG.md))
2. **`.env`** — secrets (`DATABASE_URL`, `JWT_SECRET`, SMTP, directory URL, seed vars at migrate time)

Restart uvicorn after editing `config.py`.

---

## API usage

### 1) Get a JWT

```bash
curl -sS -X POST "http://127.0.0.1:8001/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=your-password"
```

Returns `access_token` and `token_type: bearer`.

### 2) Authenticated calls

```bash
curl -sS "http://127.0.0.1:8001/users/me" \
  -H "Authorization: Bearer $TOKEN"
```

Response includes `roles` (derived from the user's assigned roles in `config.py`).

### 3) Admin API

Requires a user with `is_admin=true` (any role in `ADMIN_ROLES`).

```bash
# List users (JSON only with Bearer; browser cookie redirects to /admin)
curl -sS "http://127.0.0.1:8001/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Update roles
curl -sS -X PATCH "http://127.0.0.1:8001/admin/users/2" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"roles": ["User", "Super"]}'
```

HTML admin actions use cookie auth + CSRF on form posts (`/admin/invite`, `/admin/users/{id}/update`, etc.).

---

## Invites

1. Admin creates invite (HTML **Admin** page or `POST /invites` with Bearer).
2. Email contains link to `/invites/accept?token=...` (built from `PUBLIC_BASE_URL` + `BASE_PATH`).
3. User sets password; account is created. `grant_admin` on the invite sets admin role when accepted.

Domain allowlist: `INVITE_ALLOWED_EMAIL_DOMAINS` in `config.py`.

---

## Self-registration

When `SELF_REGISTRATION_ENABLED = True` (default):

- Guest submits email on `/register`
- Setup email sent (SMTP required)
- Same accept flow as invites

Set `SELF_REGISTRATION_ENABLED = False` for **invite-only** deployments (nav and routes disabled).

---

## Password reset

- **Request:** login page → forgot password, or `POST /password/forgot`
- **Complete:** email link → `/password/reset`, or `POST /password/reset`
- Responses are non-enumerating (always `ok` on forgot)

---

## Directory (LDAP) lookup

Optional enrichment when accepting invites or registering:

1. Set `DIRECTORY_LOOKUP_URL` in `.env` — backend calls `GET <url>?query=<email>`
2. JSON `attributes.mail` / `userPrincipalName`, optional `c` / `co` for country
3. Tune timeout/required/SSL in `config.py`

A directory “not found” does **not** block invite accept; country is set when a record exists.

---

## Deployment behind a proxy

Set in **`config.py`**:

- `BASE_PATH` — external prefix (e.g. `/connect/app`)
- `PUBLIC_BASE_URL` — browser-visible origin for emailed links

For Posit Connect embedded HTML, also consider `AUTH_COOKIE_DEPLOYMENT = "connect"`.

### Local nginx proxy

See `infra/connect-proxy/` at repo root. Example:

```bash
BACKEND_HOST=host.docker.internal BACKEND_PORT=8001 \
PROXY_PREFIX=/connect/app PROXY_MODE=preserve PROXY_PORT=8080 \
docker compose -f infra/connect-proxy/docker-compose.yml up
```

API docs: http://127.0.0.1:8080/connect/app/docs

---

## Seeding users (migrations)

**Admin** — requires `SEED_ADMIN_ENABLED=1` and `SEED_ADMIN_PASSWORD` at migrate time.

**Non-admin** — requires `SEED_USER_EMAIL` and `SEED_USER_PASSWORD` at migrate time.

Both migrations are idempotent. See [`README.md`](README.md#seeding-users) and [`CONFIG.md`](CONFIG.md).

---

## Development checks

```bash
cd user_management_api
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q tests
```

From repo root:

```bash
ruff format --check user_management_api && ruff check user_management_api
ty check user_management_api
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| White page / 500 after upgrade | Run `alembic upgrade head` (schema drift, e.g. missing `roles` column) |
| Invite links wrong host | Set `PUBLIC_BASE_URL` and `BASE_PATH` in `config.py` |
| Cookies not set on Connect | `AUTH_COOKIE_DEPLOYMENT = "connect"` or use Streamlit UI |
| Registration unavailable | `SELF_REGISTRATION_ENABLED`, SMTP, and allowed email domains |
| Weak `JWT_SECRET` rejected | Use 16+ char secret or `JWT_ALLOW_WEAK_SECRET=1` locally |
| Rate limited | `RATE_LIMIT_*` in `config.py`; trust proxy IPs for XFF |
