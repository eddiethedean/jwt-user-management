# Getting started (10 minutes)

End-to-end local setup: install → seed admin → sign in → invite a user → accept invite.

**Prerequisites:** Python 3.10+, Git (for `pip install`). See [`../README.md`](../README.md#prerequisites).

---

## 1. Install and configure

```bash
cd user_management_api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

For local dev only, add to `.env`:

```bash
JWT_ALLOW_WEAK_SECRET=1
```

### Allow test email domains

Edit [`config.py`](../config.py) — default domains are org-specific (`socom.mil`, `soc.mil`). For this tutorial:

```python
INVITE_ALLOWED_EMAIL_DOMAINS: tuple[str, ...] = ("example.com",)
```

Restart the server after editing `config.py`.

---

## 2. Create database and seed admin

```bash
SEED_ADMIN_ENABLED=1 SEED_ADMIN_PASSWORD='YourStrongPassword12' alembic upgrade head
```

This creates **`admin@example.com`** with your password (override email with `SEED_ADMIN_EMAIL` in `.env`).

---

## 3. Start the server

```bash
JWT_ALLOW_WEAK_SECRET=1 uvicorn app.asgi:app --reload --host 127.0.0.1 --port 8001
```

Open http://127.0.0.1:8001/login and sign in as `admin@example.com`.

You should land on **Admin** with the user list.

---

## 4. Invite a user (HTML)

Invites require SMTP. Add to `.env`:

```bash
SMTP_HOST=smtp.example.com
SMTP_USERNAME=your-user
SMTP_PASSWORD=your-pass
SMTP_FROM_EMAIL=noreply@example.com
```

On the **Admin** page:

1. Enter `newuser@example.com`
2. Submit **Send invite**
3. Check the outbound email for `/invites/accept?token=...`

If SMTP is not configured, invite creation returns an error (503). See [Troubleshooting](../USER_GUIDE.md#troubleshooting).

---

## 5. Accept the invite

Open the link from the email (or paste the token URL in a browser). Set a password (**minimum 12 characters**) and submit.

You should see a redirect to **Sign in**. Log in as `newuser@example.com` and land on **Account**.

---

## 6. Try the JSON API (optional)

```bash
TOKEN="$(curl -sS -X POST http://127.0.0.1:8001/auth/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=newuser@example.com&password=THE_PASSWORD_YOU_SET' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')"

curl -sS http://127.0.0.1:8001/users/me -H "Authorization: Bearer $TOKEN"
```

Full API reference: [`API.md`](API.md).

---

## What to read next

| Goal | Doc |
|------|-----|
| All settings | [`CONFIG.md`](../CONFIG.md) |
| Deployment, proxy, Connect | [`USER_GUIDE.md`](../USER_GUIDE.md) |
| Production hardening | [`SECURITY.md`](SECURITY.md) |
| HTML pages and nav | [`HTML_UI.md`](../HTML_UI.md) |
