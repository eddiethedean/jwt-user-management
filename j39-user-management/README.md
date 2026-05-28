# Backend User Management API 

This backend provides a centralized authentication service for the J39 Forms Streamlit application.

---

##  Mission Capabilities

- **HTML Forms**: Integrated Register, Login, and Admin dashboards.
- **JWT Authentication**: Secure token issuance via `/auth/token` or form login.
- **PostgreSQL Persistence**: Migrated from SQLite to a centralized J39_miso database.
- **LDAP Integration**: Automated extraction of "Given Name", "Surname", and "Country" for SOCOM users.
- **Domain Whitelisting**: Automated registration support for both `@socom.mil` and `@soc.mil` domains.
- **HTTPS Security**	Enforced "Secure" and "SameSite" cookie flags for Posit Connect SSO environments.

---

##  Run Locally (Posit Workbench)

Prereqs: **Python 3.10+**.

1. **Environment Setup**:
```bash
cd j39-user-management
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
```
Create file (`user_management_api/.env`) using .env.example as a guide
- `DATABASE_URL`: postgresql://<postgres username here>:<postgres pwd here>@postgresql.socom.mil:5432/<db name here>
- `JWT_SECRET`: <secret hashing string here>
```

2. **Initialize Server**:
Start the Uvicorn server to identify your session's dynamic proxy path.
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

3. **Align Proxy Routing**:
Restart the server with the explicit root-path to ensure HTML links and redirects function correctly behind the Workbench proxy.
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --proxy-headers --forwarded-allow-ips="*" --root-path "/s/<service_id>/p/<project_id>"
```
- Example: --root-path "/s/413ab3c9ab5a7f72b4a70/p/7c6abfd4"

If running locally with a local J39 Miso streamlit application, you must:

- UPDATE miso app.py line 22 with appropriate local port for the FastAPI

- UPDATE miso app.py line 28 with updated workbench path of the day (ie "https://workbench.socom.mil/s/413ab3c9ab5a793a754ba/p/a9b98eaf")

## Deploy to Posit Connect
This application is prepped for deployment via the publish.sh script.

Execute Deployment:

```bash
sh publish.sh
```

### Configure Production Variables (Vars Tab):

Access the Posit Connect dashboard and set the following critical mission parameters:

| Variable | Description / Example |
|---|---|
| **DATABASE_URL** | `postgresql://<user>:<pass>@postgresql.socom.mil:5432/J39_miso` |
| **JWT_SECRET** | String used for token signing. |
| **BASE_PATH** | Your assigned Vanity URL (e.g., `/api-j39-um`). |
| **PUBLIC_BASE_URL** | `https://connect.socom.mil` |

### Access Control:

**CRITICAL:** In the Posit Connect "Access" pane, set the application to **"Anyone - no login required"**. This allows the J39 Streamlit app to communicate with the API without hitting a SAML secondary wall.

## HTML Pages

- Register: `GET /register`
- Login: `GET /login`
- Users page: `GET /users?token=...` (paste token from `/login`)
- Admin page: `GET /admin?token=...` (paste token from `/login`)
- Invite accept page: `GET /invites/accept?token=...`

## JSON API

- JWT token: `POST /auth/token` (form-encoded: `username` = email, `password`)
- Current user: `GET /users/me` (Bearer)
- List users: `GET /users` (Bearer)
- Create invite (admin only): `POST /invites` (Bearer; body: `{ "email": "..." }`)
- Accept invite: `POST /invites/accept` (body: `{ "token": "...", "password": "..." }`)

## Environment Configuration

Defaults are configured in `app/core/config.py` and can be overridden via `.env` locally, or via Posit Connect **Vars** in production.

**SMTP settings:**
- `SMTP_HOST`: `smtp-relay.socom.mil`
- `SMTP_PORT`: `25`
- `SMTP_USE_TLS`: `false`
- `SMTP_FROM_EMAIL`: `no-reply-J39-Forms-App@socom.mil`

**Directory lookup:**
- `DIRECTORY_LOOKUP_URL`: `https://connect.socom.mil/api/ldapEmail`
- `DIRECTORY_LOOKUP_TIMEOUT_S`: `5`
- `DIRECTORY_LOOKUP_REQUIRED`: `false`
- `DIRECTORY_LOOKUP_VERIFY_SSL`: `false`

