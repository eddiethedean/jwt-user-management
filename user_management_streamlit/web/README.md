# Legacy HTML / CSS / JS UI

Server-rendered pages (Jinja2) with cookie-based JWT auth. Restored from the API
`app/web/archive/` tree and wired through `html_app.py`.

| Path | Purpose |
|------|---------|
| `templates/` | HTML pages (login, register, admin, invites, …) |
| `static/` | `admin/admin.js`, `admin/admin.css`, `site/forms.css` |
| `templates.py` | Jinja environment + date filters |
| `session.py` | Auth cookie helpers |
| `debug_panel.py` | Optional cookie debug overlay (`COOKIE_DEBUG=true`) |

Run the HTML app (see [`../README.md`](../README.md#legacy-html-ui-cookie-auth)).
