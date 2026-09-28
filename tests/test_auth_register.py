"""test_auth_register.py — Đăng ký, xác thực email, bootstrap admin đầu tiên."""
import re

from app.extensions import db
from app.models.user import ROLE_ADMIN, User

VALID = {
    "username": "sonnguyen",
    "email": "son@example.com",
    "password": "password123",
    "confirm_password": "password123",
}


def _read_outbox(app):
    with open(app.config["MAIL_OUTBOX_FILE"], encoding="utf-8") as f:
        return f.read()


def _extract_token(text: str) -> str:
    match = re.search(r"/verify-email/([\w-]+)", text)
    assert match, text
    return match.group(1)


def test_register_creates_unverified_user_and_sends_email(app, client, tmp_path):
    app.config["MAIL_OUTBOX_FILE"] = str(tmp_path / "outbox.log")
    response = client.post("/register", data=VALID)
    assert response.status_code == 200
    assert b"Check your email" in response.data

    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "son@example.com"))
        assert user is not None
        assert user.email_verified is False
        assert user.role != ROLE_ADMIN  # chưa xác thực -> chưa được phong admin

    assert "son@example.com" in _read_outbox(app)


def test_first_verified_user_becomes_admin(app, client, tmp_path):
    app.config["MAIL_OUTBOX_FILE"] = str(tmp_path / "outbox.log")
    client.post("/register", data=VALID)
    token = _extract_token(_read_outbox(app))

    response = client.get(f"/verify-email/{token}", follow_redirects=True)
    assert b"verified" in response.data.lower()

    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "son@example.com"))
        assert user.email_verified is True
        assert user.role == ROLE_ADMIN

    login = client.post("/login", data={"username": "sonnguyen", "password": "password123"})
    assert login.status_code == 302
    assert "/admin/rooms" in login.headers["Location"]


def test_second_verified_user_is_customer(app, client, tmp_path):
    app.config["MAIL_OUTBOX_FILE"] = str(tmp_path / "outbox.log")
    client.post("/register", data=VALID)
    client.get(f"/verify-email/{_extract_token(_read_outbox(app))}")

    client.post("/register", data={**VALID, "username": "guest2", "email": "guest2@example.com"})
    token2 = _extract_token(_read_outbox(app).splitlines()[-1] if False else _read_outbox(app))
    # lấy token của lần gửi email thứ 2 (cuối file)
    tokens = re.findall(r"/verify-email/([\w-]+)", _read_outbox(app))
    client.get(f"/verify-email/{tokens[-1]}")

    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "guest2@example.com"))
        assert user.email_verified is True
        assert user.role != ROLE_ADMIN


def test_login_blocked_until_verified(app, client, tmp_path):
    app.config["MAIL_OUTBOX_FILE"] = str(tmp_path / "outbox.log")
    client.post("/register", data=VALID)
    response = client.post("/login", data={"username": "sonnguyen", "password": "password123"})
    assert response.status_code == 401
    assert b"verify your email" in response.data.lower()


def test_register_validation_errors(client):
    response = client.post("/register", data={
        "username": "a", "email": "not-an-email", "password": "short", "confirm_password": "diff",
    })
    assert response.status_code == 422
    for field in ("username", "email", "password"):
        assert field.encode() in response.data


def test_register_duplicate_email(client):
    client.post("/register", data=VALID)
    response = client.post("/register", data={**VALID, "username": "other"})
    assert response.status_code == 409


def test_verify_invalid_token(client):
    response = client.get("/verify-email/does-not-exist", follow_redirects=True)
    assert b"invalid" in response.data.lower()


def test_resend_verification_cooldown_then_success(app, client, tmp_path):
    from datetime import datetime, timedelta, timezone

    app.config["MAIL_OUTBOX_FILE"] = str(tmp_path / "outbox.log")
    client.post("/register", data=VALID)

    # Ngay sau khi đăng ký (đã gửi 1 email) -> resend bị chặn bởi cooldown
    immediate = client.post("/resend-verification", data={"email": "son@example.com"})
    assert immediate.status_code == 429

    # Giả lập đã qua thời gian cooldown -> resend thành công
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "son@example.com"))
        user.verification_sent_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.session.commit()

    response = client.post("/resend-verification", data={"email": "son@example.com"})
    assert response.status_code == 200
    assert b"resent" in response.data.lower()


def test_resend_verification_unknown_email_is_silent(client):
    response = client.post("/resend-verification", data={"email": "nobody@example.com"})
    assert response.status_code == 200  # không tiết lộ email này chưa từng đăng ký
