## Legacy HTML UI (archived)

This backend originally shipped with a server-rendered HTML UI under:
- `app/web/templates/`
- `app/web/static/`

We are migrating the interactive UI to the Streamlit app in `streamlit_user/`.
The backend HTML routes/templates are kept **for reference and compatibility**
but should be considered **legacy** and may be removed in a future cleanup.

### What’s here
- **Auth pages**: `login.html`, `register.html`
- **Account**: `account.html`
- **Users**: `users.html`
- **Admin**: `admin.html`, `admin_user_edit.html`
- **Invite/reset pages**: `accept_invite.html`, `reset_password.html`

### Preferred UI going forward
Use the Streamlit UI (`streamlit_user/user_app.py`) as the primary browser UI.

