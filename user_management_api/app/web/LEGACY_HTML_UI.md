## Legacy HTML UI (archived)

This backend originally shipped with a server-rendered HTML UI under:
- `app/web/templates/`
- `app/web/static/`

The interactive UI lives in `user_management_streamlit/` (Streamlit and a restored
HTML app under `user_management_streamlit/web/`). This API copy under
`app/web/archive/` is kept for reference only.

### What’s here
- **Auth pages**: `login.html`, `register.html`
- **Account**: `account.html`
- **Users**: `users.html`
- **Admin**: `admin.html`, `admin_user_edit.html`
- **Invite/reset pages**: `accept_invite.html`, `reset_password.html`

### Preferred UI going forward
Use Streamlit (`user_management_streamlit/user_app.py`) or the HTML UI
(`user_management_streamlit/html_app.py`) as browser UIs; both are separate from this API process.

