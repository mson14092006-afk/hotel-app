"""test_bookings.py — Test luồng User: xem phòng, đặt phòng, huỷ booking."""

from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models.booking import Booking
from app.models.room import Room


@pytest.fixture(autouse=True)
def _require_customer_feature(app):
    """Tự động SKIP (không phải FAIL) nếu bạn chưa bật blueprint customer —
    xem hướng dẫn "MỚI" trong app/__init__.py."""
    if "customer" not in app.blueprints:
        pytest.skip("Phần User (booking) chưa được bật — xem comment 'MỚI' trong app/__init__.py")



TOMORROW = (date.today() + timedelta(days=1)).isoformat()
IN_3_DAYS = (date.today() + timedelta(days=3)).isoformat()


# Thông tin khách gửi kèm khi đặt phòng (không còn trường "guests")  
CONTACT = {"customer_name": "Nguyen Van A", "phone": "0912 345 678"}  


def _make_room(app, **overrides):
    with app.app_context():
        room = Room(
            name=overrides.get("name", "B2"),  
            quality="B",  
            type="double",  
            capacity=2,  
            total_units=overrides.get("total_units", 1),
            price_per_night=overrides.get("price_per_night", "1000000"),
            status="active",
        )
        db.session.add(room)
        db.session.commit()
        return room.id


def test_rooms_page_lists_active_rooms(app, client):
    _make_room(app)
    response = client.get("/rooms")
    assert response.status_code == 200
    assert b"B2" in response.data  #


def test_room_detail_prompts_login_when_anonymous(client, app):
    room_id = _make_room(app)
    response = client.get(f"/rooms/{room_id}")
    assert response.status_code == 200
    assert b"Login" in response.data


def test_booking_requires_login(client, app):
    room_id = _make_room(app)
    response = client.post(f"/rooms/{room_id}/book", data={
        "check_in": TOMORROW, "check_out": IN_3_DAYS, **CONTACT,  
    })
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_customer_can_book_room(customer_client, app):
    room_id = _make_room(app)
    response = customer_client.post(f"/rooms/{room_id}/book", data={
        "check_in": TOMORROW, "check_out": IN_3_DAYS, **CONTACT,  
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Booking request sent" in response.data  

    with app.app_context():
        booking = db.session.scalar(db.select(Booking))
        assert booking.customer_name == "Nguyen Van A"  
        assert booking.phone == "0912345678"  # đã bỏ khoảng trắng  
        assert str(booking.total_price) == "2000000.00"  # 2 nights * 1,000,000
        assert booking.status == "pending"  # chờ admin xem xét, không tự xác nhận  


def test_booking_requires_name_and_valid_phone(customer_client, app):  
    room_id = _make_room(app)  
    dates = {"check_in": TOMORROW, "check_out": IN_3_DAYS}  

    no_name = customer_client.post(f"/rooms/{room_id}/book", data={**dates, "customer_name": " ", "phone": "0912345678"})  
    assert no_name.status_code == 422  
    assert b"name is required" in no_name.data  

    bad_phone = customer_client.post(f"/rooms/{room_id}/book", data={**dates, "customer_name": "A", "phone": "abc"}) 
    assert bad_phone.status_code == 422 
    assert b"Phone number must have" in bad_phone.data  

    with app.app_context():  
        assert db.session.scalar(db.select(db.func.count(Booking.id))) == 0  


def test_booking_rejects_invalid_dates(customer_client, app):
    room_id = _make_room(app)
    response = customer_client.post(f"/rooms/{room_id}/book", data={
        "check_in": IN_3_DAYS, "check_out": TOMORROW, **CONTACT,  
    })
    assert response.status_code == 422


def test_booking_blocked_when_no_units_left(customer_client, app):
    room_id = _make_room(app, total_units=1)
    first = customer_client.post(f"/rooms/{room_id}/book", data={
        "check_in": TOMORROW, "check_out": IN_3_DAYS, **CONTACT,  
    })
    assert first.status_code == 302

    second = customer_client.post(f"/rooms/{room_id}/book", data={
        "check_in": TOMORROW, "check_out": IN_3_DAYS, **CONTACT,  
    })
    assert second.status_code == 422
    assert b"No units left" in second.data


def test_my_bookings_lists_only_own_bookings(customer_client, app):
    room_id = _make_room(app)
    customer_client.post(f"/rooms/{room_id}/book", data={
        "check_in": TOMORROW, "check_out": IN_3_DAYS, **CONTACT,  
    })
    response = customer_client.get("/my-bookings")
    assert response.status_code == 200
    assert b"B2" in response.data  


def test_cancel_booking(customer_client, app):
    room_id = _make_room(app)
    customer_client.post(f"/rooms/{room_id}/book", data={
        "check_in": TOMORROW, "check_out": IN_3_DAYS, **CONTACT,  
    })
    with app.app_context():
        booking_id = db.session.scalar(db.select(Booking.id))

    response = customer_client.post(f"/my-bookings/{booking_id}/cancel", follow_redirects=True)
    assert response.status_code == 200
    assert b"Booking cancelled" in response.data

    with app.app_context():
        booking = db.session.get(Booking, booking_id)
        assert booking.status == "cancelled"


def test_cannot_cancel_others_booking(customer_client, app):
    from app.models.user import ROLE_CUSTOMER, User

    room_id = _make_room(app)
    customer_client.post(f"/rooms/{room_id}/book", data={
        "check_in": TOMORROW, "check_out": IN_3_DAYS, **CONTACT,  
    })
    with app.app_context():
        booking_id = db.session.scalar(db.select(Booking.id))
        other = User(username="other", email="other@example.com", role=ROLE_CUSTOMER, email_verified=True)
        other.set_password("password123")
        db.session.add(other)
        db.session.commit()

    other_client = app.test_client()
    other_client.post("/login", data={"username": "other", "password": "password123"})
    response = other_client.post(f"/my-bookings/{booking_id}/cancel", follow_redirects=True)
    assert b"Booking not found" in response.data

    with app.app_context():
        booking = db.session.get(Booking, booking_id)
        assert booking.status == "pending"  # không bị huỷ bởi người khác  
