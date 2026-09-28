"""services/mail_service.py — Gửi email xác thực. Chỉ dùng SMTP thật."""
import smtplib
from email.message import EmailMessage

from flask import current_app


def send_verification_email(to_email: str, username: str, verify_url: str) -> None:
    """Soạn và gửi email xác thực qua SMTP thật."""
    subject = "Confirm your ET E4 Hotel account"
    body = (
        f"Hi {username},\n\n"
        f"Confirm your email to activate your ET E4 Hotel account:\n{verify_url}\n\n"
        "This link expires in 24 hours. If you didn't create this account, ignore this email.\n"
    )
    _send_smtp(to_email, subject, body)


def _send_smtp(to_email: str, subject: str, body: str) -> None:
    """Gửi qua SMTP (Gmail, Mailtrap, SES SMTP, ...)."""
    cfg = current_app.config
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = cfg["MAIL_DEFAULT_SENDER"]
    message["To"] = to_email
    message.set_content(body)

    with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10) as smtp:
        if cfg["MAIL_USE_TLS"]:
            smtp.starttls()
        if cfg["MAIL_USERNAME"]:
            smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        smtp.send_message(message)