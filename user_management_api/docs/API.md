# JSON API reference

Interactive OpenAPI docs: http://127.0.0.1:8001/docs (when running locally).

HTML form routes (`/login`, `/admin`, etc.) are excluded from OpenAPI. See [`HTML_UI.md`](../HTML_UI.md).

---

## Authentication

### Bearer JWT

Most endpoints use `Authorization: Bearer <token>`.

Obtain a token:

```http
POST /auth/token
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=your-password
```

Response:

```json
{"access_token": "<jwt>", "token_type": "bearer"}
```

### JWT claims

| Claim | Meaning |
|-------|---------|
| `sub` | User id (string) |
| `exp` / `iat` | Expiry and issued-at (from `JWT_EXPIRES_MINUTES` in `config.py`) |
| `tv` | `token_version` on the user row — invalidated on logout, password change, and password reset |

Requests with a stale `tv` receive **401** `Invalid token`.

Optional: `country` when set on the user.

### Cookie sessions (HTML only)

The HTML UI uses an HTTP-only auth cookie set by `POST /login`. Not used by the JSON API except where noted (`GET /users` redirects cookie sessions).

---

## Endpoints

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/token` | — | Issue JWT (form: `username`, `password`) |

### Users

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/users/me` | Bearer | Current user profile + `roles` |
| PATCH | `/users/me` | Bearer | Update `full_name` (JSON body) |
| POST | `/users/me/password` | Bearer | Change password; bumps `token_version` (client must re-auth) |
| GET | `/users` | Bearer (admin) | List all users (JSON). Browser cookie → redirect to `/admin` |

`GET /users/me` response fields: `id`, `email`, `full_name`, `country`, `is_active`, `is_admin`, `roles`, `created_at`.

### Admin users

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| PATCH | `/admin/users/{id}` | Bearer (admin) | Update user |
| DELETE | `/admin/users/{id}` | Bearer (admin) | Delete user (not self) |

**PATCH body** (`AdminUpdateUserRequest`): optional `full_name`, `is_active`, `roles`, `is_admin`.

- **Prefer `roles`** — list of labels from `USER_ROLES` in `config.py`. `is_admin` is synced from `ADMIN_ROLES`.
- **Legacy `is_admin`** — shorthand: `true` assigns all `ADMIN_ROLES`; `false` assigns `User`. Updates both `roles` and `is_admin` (no desync).

Admin cannot PATCH own `is_active`, `is_admin`, or `roles`.

### Invites

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/invites` | Bearer (admin) | Create invite + send email |
| POST | `/invites/lookup` | Bearer (admin) | Directory preview (`email`, `country`, `display_name`) |
| POST | `/invites/inspect` | Bearer (admin) | Token metadata (`email`, `expires_at`, `used_at`, `grant_admin`) |
| POST | `/invites/accept` | — | Accept invite, create user |

**Create invite** body:

```json
{"email": "user@example.com", "grant_admin": false}
```

Success:

```json
{"ok": true, "invite_url": "...", "expires_at": "..."}
```

### Self-registration

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/register` | — | Form: `email`. HTML if `Accept: text/html`; else JSON `{"ok": true}` |

Requires `SELF_REGISTRATION_ENABLED` in `config.py`. Same domain allowlist as invites. Sends setup email (SMTP required).

If email already exists, returns success without revealing existence (anti-enumeration).

### Password reset

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/password/forgot` | — | Request reset email (always `{"ok": true}`) |
| POST | `/password/inspect` | Bearer (admin) | Reset token metadata |
| POST | `/password/reset` | — | Set new password from token |

**Reset** body:

```json
{"token": "<raw-token>", "password": "new-password-here"}
```

Password minimum length: **12 characters**.

### Metadata

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/__meta` | — | `base_path`, `external_base` for proxy/UI clients |
| GET | `/` | — | JSON `{"ok": true, ...}` when `Accept: application/json` |

---

## Common status codes

| Code | Typical cause |
|------|----------------|
| 400 | Validation (bad password, token used/expired, domain not allowed) |
| 401 | Missing/invalid Bearer token or stale `tv` |
| 403 | CSRF failure (HTML), inactive user, non-admin |
| 409 | Invite email already has an account |
| 422 | Invalid email format, directory required but missing |
| 503 | SMTP send failed after invite/registration token was created |

### SMTP 503 detail

`POST /invites`, `POST /register`, and admin HTML invite may return **503** `Could not send ... email` when SMTP fails. An invite row may already exist in the database; retry or invalidate via a new invite.

---

## Examples

### Admin: create invite

```bash
ADMIN_TOKEN="..."  # from POST /auth/token as admin

curl -sS -X POST http://127.0.0.1:8001/invites \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "newuser@example.com", "grant_admin": false}'
```

### Accept invite

```bash
curl -sS -X POST http://127.0.0.1:8001/invites/accept \
  -H "Content-Type: application/json" \
  -d '{"token": "RAW_TOKEN_FROM_EMAIL", "password": "longpassword12"}'
```

### Update roles

```bash
curl -sS -X PATCH http://127.0.0.1:8001/admin/users/2 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"roles": ["User", "Super"]}'
```

---

## Related

- [`SECURITY.md`](SECURITY.md) — production auth and rate limits
- [`CONFIG.md`](../CONFIG.md) — `USER_ROLES`, `ADMIN_ROLES`, domains
- [`USER_GUIDE.md`](../USER_GUIDE.md) — HTML flows and deployment
