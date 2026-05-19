from email.message import EmailMessage
import smtplib

from config.settings import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM_EMAIL,
    SMTP_USE_TLS,
    SMTP_USE_SSL,
)


def smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_PORT and SMTP_FROM_EMAIL)


def send_email(to_email: str, subject: str, body: str, reply_to: str | None = None) -> None:
    if not SMTP_HOST:
        raise RuntimeError("SMTP_HOST is not configured")
    if not to_email:
        raise RuntimeError("Recipient email is missing")

    msg = EmailMessage()
    msg["From"] = SMTP_FROM_EMAIL or SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = subject or ""
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body or "")

    if SMTP_USE_SSL:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            if SMTP_USER and SMTP_PASSWORD:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
        return

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        if SMTP_USE_TLS:
            smtp.starttls()
        if SMTP_USER and SMTP_PASSWORD:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)
