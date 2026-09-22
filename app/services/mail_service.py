"""services/mail_service.py — Gửi email xác thực.

Hai backend, chọn qua MAIL_BACKEND trong .env:
  - "console" (mặc định): KHÔNG gửi email thật, chỉ ghi link xác thực ra log
    (app.logger) và ra file .dev_mail_outbox.log ở thư mục gốc — dùng khi chưa
    có SMTP thật, để bạn tự lấy link mà bấm khi phát triển.
  - "smtp": gửi qua SMTP thật bằng thông tin MAIL_* trong .env.

Tách riêng file này để sau muốn đổi sang dịch vụ email khác (SES, SendGrid, ...)
chỉ cần sửa một chỗ, route/service gọi không đổi.
"""
import smtplib
from email.message import EmailMessage

from flask import current_app


def send_verification_email(to_email: str, username: str, verify_url: str) -> None:
    """Soạn và gửi email xác thực. Không raise ra ngoài nếu SMTP lỗi — chỉ log,
    để một lỗi gửi mail không làm hỏng toàn bộ luồng đăng ký (user có thể bấm
    "Resend" lại)."""
    subject = "Confirm your ET E4 Hotel account"
    body = (
        f"Hi {username},\n\n"
        f"Confirm your email to activate your ET E4 Hotel account:\n{verify_url}\n\n"
        "This link expires in 24 hours. If you didn't create this account, ignore this email.\n"
    )

    backend = current_app.config["MAIL_BACKEND"]
    if backend == "console":
        _send_console(to_email, subject, body, verify_url)
        return
    try:
        _send_smtp(to_email, subject, body)
    except (OSError, smtplib.SMTPException) as exc:
        current_app.logger.error("Failed to send verification email to %s: %s", to_email, exc)


def _send_console(to_email: str, subject: str, body: str, verify_url: str) -> None:
    """Backend dev: log ra console + ghi vào file để dễ xem lại."""
    message = f"[DEV MAIL] To: {to_email} | Subject: {subject}\n{body}"
    current_app.logger.info(message)
    with open(current_app.config["MAIL_OUTBOX_FILE"], "a", encoding="utf-8") as outbox:
        outbox.write(message + "\n" + ("-" * 60) + "\n")


def _send_smtp(to_email: str, subject: str, body: str) -> None:
    """Backend thật: gửi qua SMTP (Gmail, mailtrap, SES SMTP, ...)."""
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
