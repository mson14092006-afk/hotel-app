"""app/services/mail_service.py — Gửi email qua Brevo HTTP API (cổng 443).
"""
import requests
from flask import current_app
from markupsafe import escape  # thêm vào phần import ở đầu file

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _send_console(to_email: str, subject: str, html_content: str) -> bool:
    """Backend 'console': chỉ in email ra log, dùng cho test/dev, không gửi thật."""
    print(f"[MAIL console] to={to_email} | subject={subject}\n{html_content}")
    return True


def _send_brevo(to_email: str, subject: str, html_content: str, to_name: str | None) -> bool:
    """Backend 'brevo': gửi email thật qua Brevo. Trả về True nếu thành công, False nếu lỗi."""
    cfg = current_app.config
    api_key = cfg.get("BREVO_API_KEY")
    sender_email = cfg.get("MAIL_SENDER_EMAIL")

    # Thiếu cấu hình thì báo lỗi rõ ràng thay vì gửi im lặng
    if not api_key or not sender_email:
        raise RuntimeError("Thiếu BREVO_API_KEY hoặc MAIL_SENDER_EMAIL")

    payload = {
        "sender": {"name": cfg.get("MAIL_SENDER_NAME", "ET E4 Hotel"), "email": sender_email},
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }
    headers = {
        "api-key": api_key,
        "accept": "application/json",
        "content-type": "application/json",
    }

    try:
        # timeout để request không làm treo worker của gunicorn
        resp = requests.post(BREVO_URL, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()  # Brevo trả 201 khi thành công
        return True
    except requests.RequestException as exc:
        # Ghi log kèm nội dung Brevo trả về để dễ debug (sender chưa verify, key sai...)
        body = exc.response.text if exc.response is not None else ""
        current_app.logger.error("[Brevo] Gửi mail lỗi: %s | %s", exc, body)
        return False


def send_email(to_email: str, subject: str, html_content: str, to_name: str | None = None) -> bool:
    """Gửi một email theo MAIL_BACKEND ('brevo' hoặc 'console'). Trả về True nếu thành công."""
    backend = current_app.config.get("MAIL_BACKEND", "brevo")

    if backend == "console":
        return _send_console(to_email, subject, html_content)
    if backend == "brevo":
        return _send_brevo(to_email, subject, html_content, to_name)

    # Giá trị lạ (gõ sai biến môi trường) thì dừng ngay để phát hiện sớm
    raise RuntimeError(f"MAIL_BACKEND không hợp lệ: {backend!r}")

def send_verification_email(to_email: str, username: str, verify_url: str) -> bool:
    """Gửi email xác thực đăng ký (được auth_service._send_verification gọi)."""
    # escape để username không chèn được HTML vào nội dung mail
    html = (
        f"<p>Xin chào {escape(username)},</p>"
        "<p>Cảm ơn bạn đã đăng ký tại ET E4 Hotel. "
        "Bấm vào liên kết dưới đây để xác thực email:</p>"
        f'<p><a href="{escape(verify_url)}">Xác thực email</a></p>'
        "<p>Nếu bạn không đăng ký, hãy bỏ qua email này.</p>"
    )
    return send_email(to_email, "Xác thực email - ET E4 Hotel", html, to_name=username)