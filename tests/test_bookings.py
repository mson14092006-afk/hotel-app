"""test_bookings.py — Test luồng User: xem phòng, đặt phòng, huỷ booking."""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models.booking import Booking
from app.models.room import Room
from app.services import booking_service


@pytest.fixture(autouse=True)
def _require_customer_feature(app):
    """Tự động SKIP (không phải FAIL) nếu bạn chưa bật blueprint customer —
    xem hướng dẫn "MỚI" trong app/__init__.py."""
    if "customer" not in app.blueprints:
        pytest.skip("Phần User (booking) chưa được bật — xem comment 'MỚI' trong app/__init__.py")



# Đặt phòng phải cách hôm nay (giờ VN) ít nhất 7 ngày
_BASE = booking_service.vn_today() + timedelta(days=booking_service.MIN_ADVANCE_DAYS)
TOMORROW = _BASE.isoformat()                       # (tên cũ) ngày nhận phòng sớm nhất hợp lệ
IN_3_DAYS = (_BASE + timedelta(days=2)).isoformat()


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
    assert b"B2" in response.data


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


def test_pending_does_not_block_but_confirmed_does(customer_client, admin_client, app):
    room_id = _make_room(app, total_units=1)
    data = {"check_in": TOMORROW, "check_out": IN_3_DAYS, **CONTACT}

    # Hai yêu cầu pending cùng ngày đều được gửi (pending chưa chặn ngày)
    assert customer_client.post(f"/rooms/{room_id}/book", data=data).status_code == 302
    assert customer_client.post(f"/rooms/{room_id}/book", data=data).status_code == 302
    with app.app_context():
        first_id, second_id = db.session.scalars(db.select(Booking.id).order_by(Booking.id)).all()

    # Admin confirm yêu cầu đầu -> ngày bị chặn
    admin_client.post(f"/admin/bookings/{first_id}/confirm")
    blocked = customer_client.post(f"/rooms/{room_id}/book", data=data)
    assert blocked.status_code == 422
    assert b"already taken" in blocked.data

    # Yêu cầu thứ hai không thể confirm nữa (đã kín)
    admin_client.post(f"/admin/bookings/{second_id}/confirm")
    with app.app_context():
        assert db.session.get(Booking, second_id).status == "pending"

    # Huỷ booking đã confirm -> ngày mở lại
    admin_client.post(f"/admin/bookings/{first_id}/cancel")
    assert customer_client.post(f"/rooms/{room_id}/book", data=data).status_code == 302


def test_unavailable_dates_endpoint(customer_client, admin_client, app, client):
    room_id = _make_room(app, total_units=1)
    customer_client.post(f"/rooms/{room_id}/book", data={
        "check_in": TOMORROW, "check_out": IN_3_DAYS, **CONTACT,
    })
    with app.app_context():
        booking_id = db.session.scalar(db.select(Booking.id))

    body = client.get(f"/rooms/{room_id}/unavailable-dates").get_json()
    assert body["min_date"] == TOMORROW
    assert body["disabled"] == []  # còn pending -> chưa chặn

    admin_client.post(f"/admin/bookings/{booking_id}/confirm")
    body = client.get(f"/rooms/{room_id}/unavailable-dates").get_json()
    # đêm 1 và 2 kín; ngày trả phòng (IN_3_DAYS) vẫn nhận khách mới
    assert body["disabled"] == [TOMORROW, (date.fromisoformat(TOMORROW) + timedelta(days=1)).isoformat()]
    assert client.get("/rooms/999/unavailable-dates").status_code == 404


def test_booking_requires_7_days_notice(customer_client, app):
    room_id = _make_room(app)
    soon = (booking_service.vn_today() + timedelta(days=3)).isoformat()
    later = (booking_service.vn_today() + timedelta(days=5)).isoformat()
    response = customer_client.post(f"/rooms/{room_id}/book", data={
        "check_in": soon, "check_out": later, **CONTACT,
    })
    assert response.status_code == 422
    assert b"at least 7 days" in response.data


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


def test_booking_accepts_ddmmyyyy_and_special_requests(customer_client, app):
    room_id = _make_room(app)
    d_in = date.fromisoformat(TOMORROW).strftime("%d/%m/%Y")
    d_out = date.fromisoformat(IN_3_DAYS).strftime("%d/%m/%Y")
    response = customer_client.post(f"/rooms/{room_id}/book", data={
        "check_in": d_in, "check_out": d_out, **CONTACT, "special_requests": "Late check-in",
    })
    assert response.status_code == 302
    with app.app_context():
        booking = db.session.scalar(db.select(Booking))
        assert booking.check_in == date.fromisoformat(TOMORROW)
        assert booking.special_requests == "Late check-in"


def test_admin_dashboard_lists_requests(admin_client, customer_client, app):
    room_id = _make_room(app)
    customer_client.post(f"/rooms/{room_id}/book", data={
        "check_in": TOMORROW, "check_out": IN_3_DAYS, **CONTACT,
    })
    response = admin_client.get("/admin")
    assert response.status_code == 200
    assert b"Dashboard" in response.data
    assert b"Room name:" in response.data and b"Nguyen Van A" in response.data
    assert b"0912345678" in response.data


def test_admin_confirm_and_cancel_hides_request(admin_client, customer_client, app):
    room_id = _make_room(app)
    customer_client.post(f"/rooms/{room_id}/book", data={
        "check_in": TOMORROW, "check_out": IN_3_DAYS, **CONTACT,
    })
    with app.app_context():
        booking_id = db.session.scalar(db.select(Booking.id))

    admin_client.post(f"/admin/bookings/{booking_id}/confirm")
    with app.app_context():
        assert db.session.get(Booking, booking_id).status == "confirmed"

    admin_client.post(f"/admin/bookings/{booking_id}/cancel")
    with app.app_context():
        assert db.session.get(Booking, booking_id).status == "cancelled"
    assert b"Nguyen Van A" not in admin_client.get("/admin").data  # đã huỷ -> không hiển thị
    assert b"Nguyen Van A" not in customer_client.get("/my-bookings").data


def test_customer_cannot_use_admin_booking_actions(customer_client):
    assert customer_client.post("/admin/bookings/1/confirm").status_code in (302, 403)


def test_search_rooms_by_type_and_dates(client, app):
    _make_room(app)  # B2, 1 unit, loại double
    assert b"B2" in client.get("/rooms").data
    assert b"B2" in client.get("/rooms?type=double").data
    assert b"B2" not in client.get("/rooms?type=family").data
    assert b"B2" in client.get(f"/rooms?type=double&check_in={TOMORROW}&check_out={IN_3_DAYS}").data
    assert b"check_out is required" in client.get(f"/rooms?check_in={TOMORROW}").data


def test_search_rooms_by_quality(client, app):
    _make_room(app)  # B2 = Standard
    assert b"B2" in client.get("/rooms?quality=B").data
    assert b"B2" not in client.get("/rooms?quality=A").data
    assert b"Unknown quality" in client.get("/rooms?quality=Z").data