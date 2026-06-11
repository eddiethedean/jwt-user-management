# Built-in HTML UI

This package serves:

- **`templates/`** — Jinja2 pages (login, register, admin, invites, password reset, …)
- **`static/`** — CSS and admin JS
- **`session.py`**, **`templates.py`**, **`debug_panel.py`** — cookie auth and rendering helpers

Routes live under **`app/routes/html_*.py`** and are mounted from **`app/web/ui.py`**.

Masthead copy (title, tag, subtitle, stack pills) is configured in **`config.py`** via
**`UI_BRAND_*`** settings.

Emailed invite and reset links use **`PUBLIC_BASE_URL`** with API paths such as `/invites/accept?token=...` (see **`app/routes/email_links.py`**).
