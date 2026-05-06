import smtplib
from email.message import EmailMessage

from app.core.config import settings


def _brand_name() -> str:
    return "User Management"


def _from_header() -> str:
    # Keep it simple: allow SMTP_FROM_EMAIL to already include a display name if desired.
    # Example: "User Management <noreply@example.com>"
    return settings.smtp_from_email


def _set_html_and_text(
    msg: EmailMessage, *, text: str, html: str
) -> None:
    # Ensure a readable fallback for clients that can't render HTML.
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")


def _wrap_html(*, title: str, preheader: str, body_html: str) -> str:
    # Basic, email-client-friendly HTML. No external assets.
    return f"""\
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      body {{
        margin: 0;
        padding: 0;
        background: #f6f7fb;
        color: #0f172a;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      }}
      .wrap {{
        width: 100%;
        padding: 24px 12px;
      }}
      .container {{
        max-width: 560px;
        margin: 0 auto;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        overflow: hidden;
      }}
      .header {{
        padding: 18px 18px 12px;
        background: #0b1020;
        color: #ffffff;
      }}
      .brand {{
        font-weight: 900;
        letter-spacing: -0.02em;
        font-size: 16px;
      }}
      .content {{
        padding: 18px;
        line-height: 1.5;
        font-size: 14px;
      }}
      .muted {{
        color: #475569;
        font-size: 13px;
      }}
      .btn {{
        display: inline-block;
        padding: 10px 14px;
        border-radius: 10px;
        background: #4f46e5;
        color: #ffffff !important;
        text-decoration: none;
        font-weight: 800;
      }}
      .panel {{
        margin-top: 14px;
        padding: 12px;
        border: 1px solid #e2e8f0;
        background: #f8fafc;
        border-radius: 12px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace;
        font-size: 12px;
        word-break: break-all;
      }}
      .footer {{
        padding: 14px 18px 18px;
        border-top: 1px solid #e2e8f0;
        background: #fbfdff;
      }}
    </style>
  </head>
  <body>
    <!-- Preheader (hidden in body but used by some clients) -->
    <div style="display:none; max-height:0; overflow:hidden; opacity:0; color:transparent;">
      {preheader}
    </div>
    <div class="wrap">
      <div class="container">
        <div class="header">
          <div class="brand">{_brand_name()}</div>
        </div>
        <div class="content">
          {body_html}
        </div>
        <div class="footer">
          <div class="muted">
            If you didn’t request this email, you can safely ignore it.
          </div>
        </div>
      </div>
      <div class="muted" style="max-width:560px; margin: 10px auto 0; text-align:center;">
        © { _brand_name() }
      </div>
    </div>
  </body>
</html>
"""


def send_invite_email(*, to_email: str, invite_url: str) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        # Email sending disabled; treat as no-op.
        return

    msg = EmailMessage()
    msg["Subject"] = "You’re invited to User Management"
    msg["From"] = _from_header()
    msg["To"] = to_email
    text = (
        "You’ve been invited to User Management.\n\n"
        f"Accept invite:\n{invite_url}\n\n"
        "If you didn’t request this, you can ignore this email.\n"
    )
    body_html = f"""\
<h2 style="margin:0 0 8px;">You’re invited</h2>
<p class="muted" style="margin:0 0 14px;">
  Someone invited you to join <strong>{_brand_name()}</strong>.
</p>
<p style="margin:0 0 14px;">
  <a class="btn" href="{invite_url}">Accept invite</a>
</p>
<p class="muted" style="margin:0;">
  If the button doesn’t work, copy and paste this link into your browser:
</p>
<div class="panel">{invite_url}</div>
"""
    html = _wrap_html(
        title="You’re invited",
        preheader="You’ve been invited — accept your invite to continue.",
        body_html=body_html,
    )
    _set_html_and_text(msg, text=text, html=html)

    with smtplib.SMTP(settings.smtp_host) as server:
        server.send_message(msg)


def send_password_reset_email(*, to_email: str, reset_url: str) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        return

    msg = EmailMessage()
    msg["Subject"] = "Password reset"
    msg["From"] = _from_header()
    msg["To"] = to_email
    text = (
        "We received a request to reset your password.\n\n"
        f"Reset your password:\n{reset_url}\n\n"
        "If you didn’t request this, you can ignore this email.\n"
    )
    body_html = f"""\
<h2 style="margin:0 0 8px;">Reset your password</h2>
<p class="muted" style="margin:0 0 14px;">
  Use the link below to reset your password.
</p>
<p style="margin:0 0 14px;">
  <a class="btn" href="{reset_url}">Reset password</a>
</p>
<p class="muted" style="margin:0;">
  If the button doesn’t work, copy and paste this link into your browser:
</p>
<div class="panel">{reset_url}</div>
"""
    html = _wrap_html(
        title="Password reset",
        preheader="Reset your password using the link inside.",
        body_html=body_html,
    )
    _set_html_and_text(msg, text=text, html=html)

    if settings.smtp_use_tls:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        server.starttls()
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)

    try:
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)
    finally:
        server.quit()

