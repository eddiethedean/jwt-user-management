import smtplib
from email.message import EmailMessage

from app.core.config import settings


def _brand_name() -> str:
    return "User Management"


def _from_header() -> str:
    # Keep it simple: allow SMTP_FROM_EMAIL to already include a display name if desired.
    # Example: "User Management <noreply@example.com>"
    return settings.smtp_from_email


def _set_html_and_text(msg: EmailMessage, *, text: str, html: str) -> None:
    # Ensure a readable fallback for clients that can't render HTML.
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")


def _wrap_html(*, title: str, preheader: str, body_html: str) -> str:
    # Minimal table-based layout with inline styles for broad email client support.
    brand = _brand_name()
    return f"""\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
  </head>
  <body style="margin:0; padding:0; background:#f6f7fb; color:#111827; font-family:Arial, Helvetica, sans-serif;">
    <div style="display:none; max-height:0; overflow:hidden; opacity:0; color:transparent;">
      {preheader}
    </div>

    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#f6f7fb; padding:24px 0;">
      <tr>
        <td align="center" style="padding:0 12px;">
          <table role="presentation" cellpadding="0" cellspacing="0" width="560" style="width:560px; max-width:560px; background:#ffffff; border:1px solid #e5e7eb; border-radius:12px;">
            <tr>
              <td style="padding:18px 18px 12px; border-bottom:1px solid #e5e7eb;">
                <div style="font-size:14px; font-weight:700; letter-spacing:0.2px; color:#111827;">{brand}</div>
              </td>
            </tr>
            <tr>
              <td style="padding:18px; font-size:14px; line-height:20px;">
                {body_html}
              </td>
            </tr>
            <tr>
              <td style="padding:14px 18px 18px; border-top:1px solid #e5e7eb; font-size:12px; line-height:18px; color:#6b7280;">
                If you didn’t request this email, you can safely ignore it.
              </td>
            </tr>
          </table>

          <div style="max-width:560px; margin:10px auto 0; font-size:12px; line-height:18px; color:#6b7280; text-align:center;">
            © {brand}
          </div>
        </td>
      </tr>
    </table>
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
<div style="font-size:18px; line-height:24px; font-weight:700; margin:0 0 8px; color:#111827;">You’re invited</div>
<div style="font-size:14px; line-height:20px; margin:0 0 14px; color:#374151;">
  Someone invited you to join <strong>{_brand_name()}</strong>.
</div>
<div style="margin:0 0 14px;">
  <a href="{invite_url}" style="display:inline-block; padding:10px 14px; background:#2563eb; color:#ffffff; text-decoration:none; border-radius:8px; font-weight:700;">
    Accept invite
  </a>
</div>
<div style="font-size:12px; line-height:18px; margin:0; color:#6b7280;">
  If the button doesn’t work, copy and paste this link into your browser:
</div>
<div style="margin-top:10px; padding:12px; border:1px solid #e5e7eb; background:#f9fafb; border-radius:10px; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size:12px; line-height:18px; word-break:break-all;">
  {invite_url}
</div>
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
<div style="font-size:18px; line-height:24px; font-weight:700; margin:0 0 8px; color:#111827;">Reset your password</div>
<div style="font-size:14px; line-height:20px; margin:0 0 14px; color:#374151;">
  We received a request to reset your password.
</div>
<div style="margin:0 0 14px;">
  <a href="{reset_url}" style="display:inline-block; padding:10px 14px; background:#2563eb; color:#ffffff; text-decoration:none; border-radius:8px; font-weight:700;">
    Reset password
  </a>
</div>
<div style="font-size:12px; line-height:18px; margin:0; color:#6b7280;">
  If the button doesn’t work, copy and paste this link into your browser:
</div>
<div style="margin-top:10px; padding:12px; border:1px solid #e5e7eb; background:#f9fafb; border-radius:10px; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size:12px; line-height:18px; word-break:break-all;">
  {reset_url}
</div>
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
