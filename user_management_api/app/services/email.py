import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_invite_email(*, to_email: str, invite_url: str) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        # Email sending disabled; treat as no-op.
        return

    msg = EmailMessage()
    msg["Subject"] = "You're invited"
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email
    msg.set_content(f"You have been invited.\n\nAccept invite: {invite_url}\n")

    with smtplib.SMTP(settings.smtp_host) as server:
        server.send_message(msg)


def send_password_reset_email(*, to_email: str, reset_url: str) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        return

    msg = EmailMessage()
    msg["Subject"] = "Password reset"
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email
    msg.set_content(f"Reset your password:\n\n{reset_url}\n")

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

