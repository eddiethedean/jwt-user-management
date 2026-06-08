# HTML UI

Server-rendered pages ship **in this API process** (same port as `/docs`). Templates and static assets:

- **Templates:** `app/web/templates/`
- **Static:** `app/web/static/` → `/static`
- **Routes:** `app/routes/` (cookie session + CSRF on mutating forms)

Older copies under `app/web/archive/` are not served.

---

## Entry points

| Path | Who | Purpose |
|------|-----|---------|
| `/` | All | Redirect: guest → login; signed-in → account or admin |
| `/login` | Guest | Sign in |
| `/register` | Guest | Self-registration (if `SELF_REGISTRATION_ENABLED`) |
| `/account` | Signed-in | Profile + password (non-admin home) |
| `/admin` | Admin | User list + invite |
| `/admin/users/{id}` | Admin | Edit user (roles, active, delete) |
| `/invites/accept` | Guest | Accept invite / finish registration |
| `/password/reset` | Guest | Set new password from email link |

`/users` with a browser cookie redirects to `/admin` (admin) or `/account` (non-admin). JSON list still works with admin Bearer token.

---

## Navigation

Set on every request by `app/web/nav_context.py` middleware (`session_email`, `is_admin`).

| State | Nav links |
|-------|-----------|
| Guest | Register* , Sign in |
| Non-admin | Account |
| Admin | Admin, Account |

\*Register hidden when `SELF_REGISTRATION_ENABLED` is `False`.

Session bar (when signed in): email + **Log out** (no duplicate Account link).

---

## Customization (`config.py`)

| Setting | Effect |
|---------|--------|
| `APP_TITLE` | Topbar title + default page `<title>` |
| `BRAND_TAG` / `BRAND_TAG_TITLE` | Demo pill (empty tag hides it) |
| `BRAND_STACK` | Technology pills under subtitle |
| `SELF_REGISTRATION_ENABLED` | Register nav, login link, `/register` routes |
| `USER_ROLES` / `ADMIN_ROLES` | Role checkboxes on edit user; `ADMIN_ROLES` drives `is_admin` |

Jinja globals registered in `app/web/templates.py`: `app_title()`, `brand_stack()`, `user_role_list(user)`, etc.

---

## Security (HTML)

- Auth cookie set on `POST /login`; cleared on `POST /logout` (bumps `token_version`)
- CSRF tokens on forms (`csrf_token` hidden field + cookie)
- Admin-only routes redirect non-admins (no user list leak on `/admin`)
- Rate limits on login, register, password change (`config.py`)

Cookie behavior: `AUTH_COOKIE_*` settings in `config.py`. Use `AUTH_COOKIE_DEPLOYMENT = "connect"` on Posit Connect.

---

## Alternate UI

[`../user_management_streamlit/`](../user_management_streamlit/) — separate Streamlit process, `BACKEND_URL` → this API. Prefer for Connect when cookies are unreliable.
