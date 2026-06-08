# User guide: `user_management_api`

How to **run**, **use**, and **deploy** the FastAPI backend and its built-in HTML UI.

| Doc | When to read |
|-----|----------------|
| [`README.md`](README.md) | Quickstart, first login, API summary |
| [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) | 10-minute tutorial |
| [`CONFIG.md`](CONFIG.md) | All settings (`config.py` + `.env`) |
| [`docs/API.md`](docs/API.md) | Full JSON API, errors, JWT |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Production hardening |
| [`HTML_UI.md`](HTML_UI.md) | Pages, nav, branding |

**Install and first login:** [`README.md`](README.md#quickstart-local) or [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md).

---

## What this service provides

- **JWT API** — bearer tokens via `POST /auth/token`
- **HTML UI** — login, account, admin (same process as the API)
- **Invites** — admins invite users; accept via link or API
- **Self-registration** — optional (`SELF_REGISTRATION_ENABLED` in `config.py`)
- **Password reset** — forgot/reset email flow
- **Configurable roles** — multi-role assignment on admin edit user (`USER_ROLES` / `ADMIN_ROLES`)
- **Directory enrichment** — optional HTTP lookup for email/country

**Alternate UI:** Streamlit in [`../user_management_streamlit/`](../user_management_streamlit/) with `BACKEND_URL` set to this API.

---

## Using the HTML UI

### Guests

- **Sign in** — `/login`
- **Register** — `/register` when `SELF_REGISTRATION_ENABLED` is `True` (sends setup email; requires SMTP)
- **Accept invite** — link from email → `/invites/accept?token=...`
- **Reset password** — `/password/reset?token=...` or forgot-password form on login page

Passwords must be at least **12 characters** on accept and reset forms.

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

Full reference: [`docs/API.md`](docs/API.md).

### 1) Get a JWT

```bash
curl -sS -X POST "http://127.0.0.1:8001/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=your-password"
```

Returns `access_token` and `token_type: bearer`. Tokens include a `tv` claim; stale tokens return 401 after logout or password change.

### 2) Authenticated calls

```bash
curl -sS "http://127.0.0.1:8001/users/me" \
  -H "Authorization: Bearer $TOKEN"
```

Response includes `roles` (from `USER_ROLES` in `config.py`).

### 3) Admin API

Requires a user with `is_admin=true` (any role in `ADMIN_ROLES`).

```bash
curl -sS "http://127.0.0.1:8001/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

curl -sS -X PATCH "http://127.0.0.1:8001/admin/users/2" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"roles": ["User", "Super"]}'
```

**Roles vs `is_admin`:** Prefer `roles` in PATCH bodies. Legacy `is_admin: true` assigns all `ADMIN_ROLES`; `is_admin: false` assigns `User`. Both update the stored `roles` column and `is_admin` flag together.

HTML admin actions use cookie auth + CSRF on form posts (`/admin/invite`, `/admin/users/{id}/update`, etc.).

---

## Invites

1. Admin creates invite (HTML **Admin** page or `POST /invites` with Bearer).
2. Email contains link to `/invites/accept?token=...` (built from `PUBLIC_BASE_URL` + `BASE_PATH`).
3. User sets password (**min 12 characters**); account is created. `grant_admin` on the invite assigns configured admin roles when accepted.

Domain allowlist: `INVITE_ALLOWED_EMAIL_DOMAINS` in `config.py` — **change this for local dev** (defaults are org-specific).

If SMTP fails after the invite row is created, the API returns **503** — see [Troubleshooting](#troubleshooting).

---

## Self-registration

When `SELF_REGISTRATION_ENABLED = True` (default):

- Guest submits email on `/register`
- Setup email sent (SMTP required)
- Same accept flow as invites

Set `SELF_REGISTRATION_ENABLED = False` for **invite-only** deployments (nav and routes disabled).

SMTP failure returns **503** with an error message (invite token may exist in DB).

---

## Password reset

- **Request:** login page → forgot password, or `POST /password/forgot`
- **Complete:** email link → `/password/reset`, or `POST /password/reset`
- Responses are non-enumerating (always `ok` on forgot)
- New password: **minimum 12 characters**; resets invalidate existing JWTs (`token_version` bump)

---

## Directory (LDAP) lookup

Optional enrichment and gating:

1. Set `DIRECTORY_LOOKUP_URL` in `.env` — backend calls `GET <url>?query=<email>`
2. JSON `attributes.mail` / `userPrincipalName`, optional `c` / `co` for country
3. Tune timeout/required/SSL in `config.py`

### Per-endpoint behavior

| Action | `DIRECTORY_LOOKUP_REQUIRED=False` | `DIRECTORY_LOOKUP_REQUIRED=True` |
|--------|-----------------------------------|----------------------------------|
| `POST /invites` (create) | Lookup optional; 404 → proceed | No match or lookup error → **422** |
| `POST /register` | Lookup optional; errors swallowed → proceed | No match → **400**; lookup exception → **400** "not found" |
| Admin HTML invite | Lookup optional | No match → error page |
| Invite **accept** | Best-effort country from directory | **Not blocked** — accept always validates token/password only |

Lookup errors on **API invite create** return `"directory lookup failed"` (422). Self-registration maps failures to `"Email not found in directory"` (400).

---

## Deployment behind a proxy

Set in **`config.py`**:

- `BASE_PATH` — external prefix (e.g. `/connect/app`)
- `PUBLIC_BASE_URL` — browser-visible origin for emailed links

For Posit Connect embedded HTML, also consider `AUTH_COOKIE_DEPLOYMENT = "connect"`. See [`docs/SECURITY.md`](docs/SECURITY.md).

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

See [`README.md`](README.md#development-checks).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Cannot log in after install | Database is empty — seed admin per [`README.md`](README.md#first-login-required) |
| Registration / invite "domain not allowed" | Add your domain to `INVITE_ALLOWED_EMAIL_DOMAINS` in `config.py` |
| Invite/register returns 503 | Configure SMTP in `.env`; a token row may exist — retry or create new invite |
| White page / 500 after upgrade | Run `alembic upgrade head` (schema drift, e.g. missing `roles` column) |
| Invite links wrong host | Set `PUBLIC_BASE_URL` and `BASE_PATH` in `config.py` |
| Cookies not set on Connect | `AUTH_COOKIE_DEPLOYMENT = "connect"` or use Streamlit UI |
| Registration unavailable | `SELF_REGISTRATION_ENABLED`, SMTP, and allowed email domains |
| Weak `JWT_SECRET` rejected | Use 16+ char secret or `JWT_ALLOW_WEAK_SECRET=1` locally |
| Rate limited | `RATE_LIMIT_*` in `config.py`; trust proxy IPs for XFF |
| 401 after password change | Expected — re-login; HTML account page re-issues cookie automatically |
| Directory required but invite fails | Check `DIRECTORY_LOOKUP_URL`, CA bundle, and `DIRECTORY_LOOKUP_VERIFY_SSL` |
