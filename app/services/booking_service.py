"""services/booking_service.py — Business logic cho Booking (xem phòng trống, đặt phòng, huỷ)."""
import re  
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models.booking import ACTIVE_BOOKING_STATUSES, STATUS_CANCELLED, STATUS_PENDING, Booking  
from app.models.room import STATUS_ACTIVE, Room
from app.services.errors import NotFoundError, ValidationError

MAX_STAY_NIGHTS = 30
CUSTOMER_NAME_MAX = 120  
# Số điện thoại: sau khi bỏ khoảng trắng/dấu chấm/gạch ngang, chỉ gồm 9-15 chữ số (cho phép + đầu). 
PHONE_PATTERN = re.compile(r"^\+?\d{9,15}$")  # <== MỚI SỬA


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


def _validate_booking_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError({"_": "Invalid form data."})

    errors: dict[str, str] = {}
    clean: dict = {}

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
            clean["check_in"] = check_in
            clean["check_out"] = check_out

    name = payload.get("customer_name")  
    if not isinstance(name, str) or not name.strip():  
        errors["customer_name"] = "Your name is required."  
    elif len(name.strip()) > CUSTOMER_NAME_MAX:  
        errors["customer_name"] = f"Name must be at most {CUSTOMER_NAME_MAX} characters."  
    else:  
        clean["customer_name"] = name.strip()  

    phone_raw = payload.get("phone")  
    if not isinstance(phone_raw, str) or not phone_raw.strip():  
        errors["phone"] = "Phone number is required."  
    else:  
        phone = re.sub(r"[\s.\-()]", "", phone_raw)  
        if PHONE_PATTERN.match(phone):
            clean["phone"] = phone  
        else:  
            errors["phone"] = "Phone number must have 9-15 digits (a leading + is allowed)."  

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


def get_bookable_room(room_id: int) -> Room:
    room = db.session.get(Room, room_id)
    if room is None or room.status != STATUS_ACTIVE:
        raise NotFoundError("Room not found.")
    return room


def create_booking(user, room_id: int, payload: dict) -> Booking:
    """Validate + tạo yêu cầu đặt phòng (status pending) cho `user` hiện tại.  # <== MỚI SỬA

    Số khách không nhập: loại phòng đã quy định (A1 = 1 người, B4 = 4 người...).  # <== MỚI SỬA
    Raise ValidationError nếu dữ liệu sai hoặc hết phòng trong khoảng ngày đó.  # <== MỚI SỬA
    """  # <== MỚI SỬA
    room = get_bookable_room(room_id)
    data = _validate_booking_payload(payload)

    booked = _units_booked(room.id, data["check_in"], data["check_out"])
    if booked >= room.total_units:
        raise ValidationError({"_": "No units left for the selected dates. Try different dates."})

    nights = (data["check_out"] - data["check_in"]).days
    total_price = (Decimal(room.price_per_night) * nights).quantize(Decimal("0.01"))

    booking = Booking(
        user_id=user.id,
        room_id=room.id,
        customer_name=data["customer_name"],  
        phone=data["phone"],  
        check_in=data["check_in"],
        check_out=data["check_out"],
        total_price=total_price,
        status=STATUS_PENDING,  # chờ admin xem xét / tư vấn rồi mới xác nhận  # <== MỚI SỬA
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