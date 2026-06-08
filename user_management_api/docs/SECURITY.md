# Security guide

Production-oriented checklist for `user_management_api`. Not a formal threat model; use this for deployment reviews and hardening.

---

## Authentication modes

| Mode | Used by | Storage |
|------|---------|---------|
| **Bearer JWT** | JSON API clients | Client stores token; send `Authorization: Bearer ...` |
| **HTTP-only cookie** | HTML UI | Set on `POST /login`; cleared on `POST /logout` |

Both use the same JWT signing key (`JWT_SECRET` in `.env`). Cookie sessions include the `tv` (`token_version`) claim.

### Session invalidation

`token_version` increments on:

- `POST /logout` (HTML)
- Password change (`POST /users/me/password`, HTML `/account/password`)
- Password reset (`POST /password/reset`)

Stale tokens return **401**. HTML password change re-issues the cookie; API clients must call `POST /auth/token` again.

---

## Production checklist

### Secrets (`.env`)

- [ ] Set **`JWT_SECRET`** to a random string **≥ 16 characters** (do not use `dev-secret` in production)
- [ ] Do **not** set `JWT_ALLOW_WEAK_SECRET` in production
- [ ] Use a production database URL (`DATABASE_URL`) — not default SQLite for multi-instance deploys
- [ ] Store SMTP credentials in `.env` only; restrict file permissions

### Transport

- [ ] Serve over **HTTPS** in production
- [ ] Set `AUTH_COOKIE_SECURE = True` in `config.py` when not inferring from request
- [ ] If `AUTH_COOKIE_SAMESITE = "none"`, `Secure` must be true (enforced in code)

### Cookies (HTML UI)

- [ ] `AUTH_COOKIE_DEPLOYMENT = "connect"` on Posit Connect embedded HTML
- [ ] Prefer Streamlit UI on Connect when cookies are unreliable ([`USER_GUIDE.md`](../USER_GUIDE.md))
- [ ] Leave `COOKIE_DEBUG = False` in production

### Access control

- [ ] Set `INVITE_ALLOWED_EMAIL_DOMAINS` to your organization’s domains
- [ ] Set `SELF_REGISTRATION_ENABLED = False` for invite-only deployments
- [ ] Review `USER_ROLES` / `ADMIN_ROLES` — `ADMIN_ROLES` must be a subset of `USER_ROLES`
- [ ] Use `DIRECTORY_LOOKUP_REQUIRED` when directory proof is mandatory for new invites/registration

### Rate limiting

- [ ] Keep `RATE_LIMIT_ENABLED = True`
- [ ] Tune `RATE_LIMIT_AUTH_PER_MINUTE` for your traffic
- [ ] Set `RATE_LIMIT_TRUSTED_PROXIES` to your reverse-proxy IPs if using `X-Forwarded-For` for client keys
- [ ] Add proxy-level rate limits for multi-worker deployments (in-process limits are per worker)

### Email and tokens

- [ ] Configure SMTP before enabling invites or self-registration
- [ ] Set `PUBLIC_BASE_URL` and `BASE_PATH` so emailed links hit your public host
- [ ] Invite and reset tokens are single-use and time-limited

### Database

- [ ] Run `alembic upgrade head` on deploy
- [ ] Do not commit `.env` or production secrets
- [ ] Seed admin only via controlled migrate-time env (`SEED_ADMIN_ENABLED=1`), not weak defaults

---

## CSRF (HTML forms)

Mutating HTML endpoints validate a CSRF token (hidden field + cookie). JSON API endpoints use Bearer auth and do not use CSRF.

Admin HTML actions protected: login, logout, register, account update, password change, admin invite, user edit/delete.

---

## Non-enumeration

- `POST /password/forgot` always returns `{"ok": true}` whether the email exists
- Self-registration returns success for existing accounts (no email sent)

---

## Password policy

- Minimum length: **12 characters** (`MIN_PASSWORD_LENGTH` in code)
- Seed passwords at migrate time: min 12 chars; weak known passwords rejected

---

## What this service does not provide

- OAuth / SAML / social login
- MFA / TOTP
- Audit log of admin actions
- Per-endpoint RBAC beyond admin vs non-admin + configurable role labels
- Centralized session store (JWT + `token_version` only)

For enterprise SSO, place this API behind an identity gateway or use the Streamlit UI with your org’s auth proxy.

---

## Related

- [`API.md`](API.md) — JWT claims and error codes
- [`CONFIG.md`](../CONFIG.md) — all security-related settings
- [`HTML_UI.md`](../HTML_UI.md) — cookie and CSRF behavior
