"""test_layouts.py — Test tách giao diện client / admin.
"""
import pytest
from jinja2 import nodes

from app.models.user import ROLE_ADMIN
from tests.conftest import _make_user


@pytest.fixture(autouse=True)
def _require_split_layout(app):
    """SKIP nếu chưa bật blueprint hoặc chưa bật dòng extends trong base.html."""
    if "customer" not in app.blueprints or "admin_home" not in app.blueprints:
        pytest.skip("Chưa bật blueprint customer/admin_home — xem khối MỚI trong app/__init__.py")
    source = app.jinja_env.loader.get_source(app.jinja_env, "base.html")[0]
    if not list(app.jinja_env.parse(source).find_all(nodes.Extends)):
        pytest.skip("Chưa bật dòng extends trong base.html")


def _html(response):
    return response.get_data(as_text=True)


def test_anonymous_sees_client_navbar(client):
    html = _html(client.get("/"))
    assert "ET E4 Hotel" in html
    assert ">Home<" in html
    assert "Khám phá" in html
    assert "Login" in html
    assert "Edit room" not in html
    assert "Hello Admin" not in html


def test_customer_navbar_has_rooms_and_bookings_but_no_admin_link(customer_client):
    html = _html(customer_client.get("/"))
    assert "Khám phá" in html
    assert 'href="/my-bookings"' in html
    assert "Logout" in html
    assert "Edit room" not in html


def test_client_home_has_welcome_and_search_bar(client):
    html = _html(client.get("/"))
    assert "Welcome to our hotel" in html
    assert 'name="check_in"' in html and 'name="check_out"' in html
    for room_type in ("single", "double", "twin", "family", "suite"):
        assert f'value="{room_type}"' in html


def test_customer_cannot_open_admin_pages(customer_client):
    assert customer_client.get("/admin").status_code == 403
    assert customer_client.get("/admin/rooms").status_code == 403


def test_anonymous_admin_page_redirects_to_login(client):
    response = client.get("/admin")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_admin_home_redirects_to_hello_admin(admin_client):
    response = admin_client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin")


def test_hello_admin_page_uses_admin_navbar_only(admin_client):
    html = _html(admin_client.get("/admin"))
    assert "Hello Admin" in html
    assert "Edit room" in html
    assert 'href="/rooms"' not in html
    assert "My bookings" not in html


def test_admin_rooms_page_keeps_csrf_meta_for_js(admin_client):
    html = _html(admin_client.get("/admin/rooms"))
    assert 'name="csrf-token"' in html
    assert 'href="/rooms"' not in html


def test_admin_login_lands_on_hello_admin(app):
    _make_user("boss", ROLE_ADMIN)
    response = app.test_client().post("/login", data={"username": "boss", "password": "password123"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin")


def test_customer_login_lands_on_home(app):
    _make_user("guest9", "customer")
    response = app.test_client().post("/login", data={"username": "guest9", "password": "password123"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
