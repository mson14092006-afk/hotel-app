"""test_search.py — Trang "Khám phá" (/rooms) và tìm phòng theo loại phòng / khoảng ngày.

CHỈ CHẠY SAU KHI bật blueprint customer (xem khối MỚI trong app/__init__.py); trước đó tự SKIP.
"""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models.booking import Booking
from app.models.room import Room
from app.models.user import ROLE_CUSTOMER, User
from tests.conftest import _make_user


def D(days: int) -> str:
    """Ngày hôm nay + days, dạng YYYY-MM-DD."""
    return (date.today() + timedelta(days=days)).isoformat()


@pytest.fixture(autouse=True)
def _require_customer_feature(app):
    if "customer" not in app.blueprints:
        pytest.skip("Phần User chưa được bật — xem khối MỚI trong app/__init__.py")


def _html(response):
    return response.get_data(as_text=True)


def _add_room(app, name, room_type="twin", total_units=1, status="active"):
    with app.app_context():
        room = Room(name=name, type=room_type, capacity=2, total_units=total_units,
                    price_per_night="1000000", status=status)
        db.session.add(room)
        db.session.commit()
        return room.id


def _book(app, room_id, check_in, check_out, status="confirmed"):
    with app.app_context():
        user_id = db.session.scalar(db.select(User.id))
        db.session.add(Booking(user_id=user_id, room_id=room_id, guests=1, check_in=date.fromisoformat(check_in),
                               check_out=date.fromisoformat(check_out), total_price=1000000, status=status))
        db.session.commit()


def test_kham_pha_lists_only_active_rooms(client, app):
    _add_room(app, "Visible Room")
    _add_room(app, "Hidden Room", status="inactive")
    response = client.get("/rooms")
    html = _html(response)
    assert response.status_code == 200
    assert "Khám phá" in html
    assert "Visible Room" in html
    assert "Hidden Room" not in html


def test_search_bar_offers_all_room_types(client):
    html = _html(client.get("/rooms"))
    for room_type in ("single", "double", "twin", "family", "suite"):
        assert f'value="{room_type}"' in html


def test_search_filters_by_type(client, app):
    _add_room(app, "Twin One", "twin")
    _add_room(app, "Suite One", "suite")
    html = _html(client.get("/rooms?type=suite"))
    assert "Suite One" in html
    assert "Twin One" not in html


def test_search_excludes_room_with_no_unit_left_for_dates(client, app):
    only_one = _add_room(app, "Only One", total_units=1)
    has_spare = _add_room(app, "Has Spare", total_units=2)
    _make_user("guest", ROLE_CUSTOMER)
    _book(app, only_one, D(2), D(4))
    _book(app, has_spare, D(2), D(4))

    overlapping = _html(client.get(f"/rooms?check_in={D(3)}&check_out={D(5)}"))
    assert "Only One" not in overlapping   # hết unit trong khoảng ngày
    assert "Has Spare" in overlapping      # còn 1 unit trống

    # check-in trùng ngày check-out của booking cũ -> không giao nhau -> phòng vẫn trống
    adjacent = _html(client.get(f"/rooms?check_in={D(4)}&check_out={D(6)}"))
    assert "Only One" in adjacent


def test_cancelled_booking_does_not_block_search(client, app):
    room_id = _add_room(app, "Was Booked", total_units=1)
    _make_user("guest", ROLE_CUSTOMER)
    _book(app, room_id, D(2), D(4), status="cancelled")
    assert "Was Booked" in _html(client.get(f"/rooms?check_in={D(2)}&check_out={D(4)}"))


def test_search_needs_both_dates(client):
    response = client.get(f"/rooms?check_in={D(2)}")
    assert response.status_code == 422
    assert "check_out is required" in _html(response)


def test_search_rejects_past_dates_and_bad_order(client):
    assert "in the past" in _html(client.get(f"/rooms?check_in={D(-2)}&check_out={D(2)}"))
    assert client.get(f"/rooms?check_in={D(5)}&check_out={D(2)}").status_code == 422


def test_search_rejects_unknown_room_type(client):
    response = client.get("/rooms?type=castle")
    assert response.status_code == 422
    assert "Unknown room type" in _html(response)


def test_no_match_shows_message(client, app):
    _add_room(app, "Twin One", "twin")
    assert "No rooms match your search" in _html(client.get("/rooms?type=suite"))


def test_room_detail_prefills_searched_dates(customer_client, app):
    # Form ngày chỉ hiện khi đã đăng nhập (anonymous chỉ thấy link Login/register).
    room_id = _add_room(app, "Prefill Room")
    html = _html(customer_client.get(f"/rooms/{room_id}?check_in={D(2)}&check_out={D(4)}"))
    assert f'value="{D(2)}"' in html
    assert f'value="{D(4)}"' in html
