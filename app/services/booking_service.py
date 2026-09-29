"""services/booking_service.py — Business logic cho Booking (xem phòng trống, đặt phòng, huỷ)."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models.booking import ACTIVE_BOOKING_STATUSES, STATUS_CANCELLED, STATUS_CONFIRMED, Booking
from app.models.room import ROOM_TYPES, STATUS_ACTIVE, Room
from app.services.errors import NotFoundError, ValidationError

MAX_STAY_NIGHTS = 30


def _parse_date(payload: dict, field: str, errors: dict):
    raw = payload.get(field)
    if not raw:
        errors[field] = f"{field} is required."
        return None
    try:
        return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
    except ValueError:
        errors[field] = f"{field} must be a valid date (YYYY-MM-DD)."
        return None


def _validate_stay_dates(payload: dict, errors: dict) -> dict:
    """Kiểm tra cặp ngày check_in/check_out (dùng chung cho đặt phòng và tìm phòng).
    Trả {"check_in": date, "check_out": date} nếu hợp lệ, ngược lại ghi lỗi vào `errors`."""
    check_in = _parse_date(payload, "check_in", errors)
    check_out = _parse_date(payload, "check_out", errors)
    if check_in and check_out:
        if check_in < date.today():
            errors["check_in"] = "Check-in date cannot be in the past."
        elif check_out <= check_in:
            errors["check_out"] = "Check-out date must be after check-in date."
        elif (check_out - check_in).days > MAX_STAY_NIGHTS:
            errors["check_out"] = f"Stay cannot be longer than {MAX_STAY_NIGHTS} nights."
        else:
            return {"check_in": check_in, "check_out": check_out}
    return {}


def _validate_booking_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError({"_": "Invalid form data."})

    errors: dict[str, str] = {}
    clean: dict = {}

    clean.update(_validate_stay_dates(payload, errors))

    guests_raw = payload.get("guests")
    try:
        guests = int(guests_raw)
        if guests <= 0:
            raise ValueError
        clean["guests"] = guests
    except (TypeError, ValueError):
        errors["guests"] = "Guests must be a positive whole number."

    if errors:
        raise ValidationError(errors)
    return clean


def _units_booked(room_id: int, check_in: date, check_out: date, exclude_booking_id: int | None = None) -> int:
    """Số phòng (units) đã bị chiếm trong khoảng [check_in, check_out) — 2 khoảng
    ngày giao nhau khi check_in_a < check_out_b AND check_out_a > check_in_b."""
    stmt = db.select(func.count(Booking.id)).where(
        Booking.room_id == room_id,
        Booking.status.in_(ACTIVE_BOOKING_STATUSES),
        Booking.check_in < check_out,
        Booking.check_out > check_in,
    )
    if exclude_booking_id:
        stmt = stmt.where(Booking.id != exclude_booking_id)
    return db.session.scalar(stmt) or 0


def list_active_rooms():
    """Danh sách phòng đang mở bán, cho trang xem phòng công khai."""
    stmt = db.select(Room).where(Room.status == STATUS_ACTIVE).order_by(Room.price_per_night)
    return list(db.session.scalars(stmt))


def search_rooms(room_type: str | None = None, check_in: str | None = None, check_out: str | None = None):
    """Tìm phòng đang mở bán (status = active) theo loại phòng và/hoặc khoảng ngày.

    - Không truyền gì: trả tất cả phòng active ("Khám phá").
    - Truyền `room_type`: chỉ lấy loại đó (phải thuộc ROOM_TYPES).
    - Truyền ngày: phải có CẢ check_in và check_out hợp lệ; chỉ giữ phòng còn ít nhất
      1 unit trống trong cả khoảng ngày (số booking pending/confirmed giao khoảng đó < total_units).
    Raise ValidationError nếu tham số sai. Ngày là chuỗi YYYY-MM-DD (lấy thẳng từ query string).
    """
    errors: dict[str, str] = {}
    room_type = (room_type or "").strip()
    check_in = (check_in or "").strip()
    check_out = (check_out or "").strip()

    if room_type and room_type not in ROOM_TYPES:
        errors["type"] = "Unknown room type."
    dates = {}
    if check_in or check_out:
        dates = _validate_stay_dates({"check_in": check_in, "check_out": check_out}, errors)
    if errors:
        raise ValidationError(errors)

    stmt = db.select(Room).where(Room.status == STATUS_ACTIVE).order_by(Room.price_per_night)
    if room_type:
        stmt = stmt.where(Room.type == room_type)
    rooms = list(db.session.scalars(stmt))

    if dates:
        # 1 query gộp: số booking đang giữ chỗ theo từng phòng trong khoảng ngày cần tìm
        booked = dict(
            db.session.execute(
                db.select(Booking.room_id, func.count(Booking.id))
                .where(
                    Booking.status.in_(ACTIVE_BOOKING_STATUSES),
                    Booking.check_in < dates["check_out"],
                    Booking.check_out > dates["check_in"],
                )
                .group_by(Booking.room_id)
            ).all()
        )
        rooms = [room for room in rooms if booked.get(room.id, 0) < room.total_units]
    return rooms


def get_bookable_room(room_id: int) -> Room:
    room = db.session.get(Room, room_id)
    if room is None or room.status != STATUS_ACTIVE:
        raise NotFoundError("Room not found.")
    return room


def create_booking(user, room_id: int, payload: dict) -> Booking:
    """Validate + tạo booking cho `user` hiện tại. Raise ValidationError nếu hết phòng."""
    room = get_bookable_room(room_id)
    data = _validate_booking_payload(payload)

    if data["guests"] > room.capacity:
        raise ValidationError({"guests": f"This room fits at most {room.capacity} guest(s)."})

    booked = _units_booked(room.id, data["check_in"], data["check_out"])
    if booked >= room.total_units:
        raise ValidationError({"_": "No units left for the selected dates. Try different dates."})

    nights = (data["check_out"] - data["check_in"]).days
    total_price = (Decimal(room.price_per_night) * nights).quantize(Decimal("0.01"))

    booking = Booking(
        user_id=user.id,
        room_id=room.id,
        guests=data["guests"],
        check_in=data["check_in"],
        check_out=data["check_out"],
        total_price=total_price,
        status=STATUS_CONFIRMED,  # chưa có luồng thanh toán/duyệt -> xác nhận ngay
    )
    db.session.add(booking)
    db.session.commit()
    return booking


def list_user_bookings(user):
    stmt = (
        db.select(Booking)
        .where(Booking.user_id == user.id)
        .order_by(Booking.check_in.desc())
    )
    return list(db.session.scalars(stmt))


def cancel_booking(user, booking_id: int) -> Booking:
    """Huỷ booking — chỉ chủ booking mới huỷ được, và chỉ khi chưa tới ngày nhận phòng."""
    booking = db.session.get(Booking, booking_id)
    if booking is None or booking.user_id != user.id:
        raise NotFoundError("Booking not found.")
    if booking.status == STATUS_CANCELLED:
        return booking
    if booking.check_in <= date.today():
        raise ValidationError({"_": "Cannot cancel a booking that has already started."})

    booking.status = STATUS_CANCELLED
    db.session.commit()
    return booking
