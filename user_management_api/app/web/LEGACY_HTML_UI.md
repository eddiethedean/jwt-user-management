# HTML UI (restored)

The server-rendered HTML UI is served from this API process again (same port as `/docs`).

- **Templates**: `app/web/templates/`
- **Static assets**: `app/web/static/` (mounted at `/static`)
- **Routes**: cookie-auth HTML handlers in `app/routes/` alongside the JSON API

Entry points: `/`, `/register`, `/login`, `/admin`, `/users`, `/account`.

The standalone `user_management_streamlit/html_app.py` remains available as an alternate deployment option.
