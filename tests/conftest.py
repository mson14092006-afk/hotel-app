"""conftest.py — Fixture dùng chung cho test: app, DB sạch, client đã đăng nhập admin."""
import pytest

from app import create_app
from app.extensions import db
from app.models.user import ROLE_ADMIN, ROLE_CUSTOMER, User


@pytest.fixture()
def app():
    """App ở chế độ testing với DB trống cho mỗi test."""
    app = create_app("testing")
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
