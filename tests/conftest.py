"""conftest.py — Fixture dùng chung cho test: app, DB sạch, client đã đăng nhập admin."""
import pytest
from flask import current_app

from app import create_app
from app.extensions import db
from app.models.user import ROLE_ADMIN, ROLE_CUSTOMER, User


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch):
    """Test không bao giờ gửi mail thật: thay _send_smtp bằng hàm ghi nội dung mail vào MAIL_OUTBOX_FILE."""

    def fake_send(to_email, subject, body):
        with open(current_app.config["MAIL_OUTBOX_FILE"], "a", encoding="utf-8") as outbox:
            outbox.write(f"[TEST MAIL] To: {to_email} | Subject: {subject}\n{body}\n")

    monkeypatch.setattr("app.services.mail_service._send_smtp", fake_send)


@pytest.fixture()
def app(tmp_path):
    """App ở chế độ testing với DB trống cho mỗi test."""
    app = create_app("testing")
    app.config["MAIL_OUTBOX_FILE"] = str(tmp_path / "outbox.log")  # mỗi test một file outbox riêng
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(username: str, role: str) -> None:
    user = User(
        username=username, email=f"{username}@example.com", role=role, email_verified=True
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()


@pytest.fixture()
def client(app):
    """Client chưa đăng nhập."""
    return app.test_client()


@pytest.fixture()
def admin_client(app):
    """Client đã đăng nhập bằng tài khoản admin."""
    _make_user("admin", ROLE_ADMIN)
    client = app.test_client()
    client.post("/login", data={"username": "admin", "password": "password123"})
    return client


@pytest.fixture()
def customer_client(app):
    """Client đã đăng nhập bằng tài khoản khách (không phải admin)."""
    _make_user("guest", ROLE_CUSTOMER)
    client = app.test_client()
    client.post("/login", data={"username": "guest", "password": "password123"})
    return client
