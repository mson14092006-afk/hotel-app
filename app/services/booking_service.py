"""services/booking_service.py — Business logic cho Booking (xem phòng trống, đặt phòng, huỷ)."""
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models.booking import (
    ACTIVE_BOOKING_STATUSES,
    STATUS_CANCELLED,
    STATUS_CONFIRMED,
    STATUS_PENDING,
    Booking,
)
from app.models.room import ROOM_QUALITIES, ROOM_TYPES, STATUS_ACTIVE, Room
from app.services.errors import NotFoundError, ValidationError

MAX_STAY_NIGHTS = 30
MIN_ADVANCE_DAYS = 7  # ngày nhận phòng sớm nhất = hôm nay (giờ Việt Nam) + 7 ngày
VN_TZ = timezone(timedelta(hours=7))
CUSTOMER_NAME_MAX = 120
SPECIAL_REQUESTS_MAX = 1000
# Số điện thoại: sau khi bỏ khoảng trắng/dấu chấm/gạch ngang, chỉ gồm 9-15 chữ số (cho phép + đầu).
PHONE_PATTERN = re.compile(r"^\+?\d{9,15}$")


def vn_today() -> date:
    """Ngày hôm nay theo giờ Việt Nam (không phụ thuộc múi giờ của server/container)."""
    return datetime.now(VN_TZ).date()


def earliest_check_in() -> date:
    return vn_today() + timedelta(days=MIN_ADVANCE_DAYS)


def _parse_date(payload: dict, field: str, errors: dict):
    raw = payload.get(field)
    if not raw:
        errors[field] = f"{field} is required."
        return None
    text = str(raw).strip()
    # Khách nhập ngày/tháng/năm (dd/mm/yyyy); vẫn chấp nhận yyyy-mm-dd để tương thích.
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    errors[field] = f"{field} must be a valid date (dd/mm/yyyy)."
    return None


def _validate_booking_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError({"_": "Invalid form data."})

    errors: dict[str, str] = {}
    clean: dict = {}

    check_in = _parse_date(payload, "check_in", errors)
    check_out = _parse_date(payload, "check_out", errors)
    if check_in and check_out:
        if check_in < earliest_check_in():
            errors["check_in"] = (
                f"Check-in must be at least {MIN_ADVANCE_DAYS} days from today "
                f"(earliest: {earliest_check_in().strftime('%d/%m/%Y')})."
            )
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

    special = payload.get("special_requests")
    if special is None or (isinstance(special, str) and not special.strip()):
        clean["special_requests"] = None
    elif not isinstance(special, str):
        errors["special_requests"] = "Special requests must be text."
    elif len(special.strip()) > SPECIAL_REQUESTS_MAX:
        errors["special_requests"] = f"Special requests must be at most {SPECIAL_REQUESTS_MAX} characters."
    else:
        clean["special_requests"] = special.strip()

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


def search_rooms(room_type, check_in_raw, check_out_raw, quality=None):
    """Tìm phòng đang mở bán theo chất lượng (A/B), loại phòng và (tuỳ chọn) khoảng ngày còn trống.

    Để trống cả hai ngày = chỉ lọc theo loại. Nhập ngày thì phải nhập cả hai.
    """
    errors = {}
    if room_type and room_type not in ROOM_TYPES:
        errors["type"] = "Unknown room type."
    if quality and quality not in ROOM_QUALITIES:
        errors["quality"] = "Unknown quality."
    check_in = check_out = None
    if check_in_raw or check_out_raw:
        check_in = _parse_date({"check_in": check_in_raw}, "check_in", errors)
        check_out = _parse_date({"check_out": check_out_raw}, "check_out", errors)
        if check_in and check_out and check_out <= check_in:
            errors["check_out"] = "check_out must be after check_in."
    if errors:
        raise ValidationError(errors)

    rooms = list_active_rooms()
    if quality:
        rooms = [r for r in rooms if r.quality == quality]
    if room_type:
        rooms = [r for r in rooms if r.type == room_type]
    if check_in and check_out:
        rooms = [r for r in rooms if _units_booked(r.id, check_in, check_out) < r.total_units]
    return rooms


def unavailable_dates(room: Room) -> dict:
    """Các đêm đã KÍN của phòng (đủ total_units booking đã confirmed) cho lịch chọn ngày.

    Trả về {"min_date": "YYYY-MM-DD", "disabled": ["YYYY-MM-DD", ...]}. Ngày trả phòng không
    tính là đêm bị chiếm (đặt 5/10 -> 7/10 chiếm đêm 5 và 6, ngày 7 vẫn nhận khách mới).
    """
    min_date = earliest_check_in()
    rows = db.session.execute(
        db.select(Booking.check_in, Booking.check_out).where(
            Booking.room_id == room.id,
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
            Booking.check_out > min_date,
        )
    ).all()
    per_night = Counter()
    for check_in, check_out in rows:
        night = max(check_in, min_date)
        while night < check_out:
            per_night[night] += 1
            night += timedelta(days=1)
    disabled = sorted(d.isoformat() for d, count in per_night.items() if count >= room.total_units)
    return {"min_date": min_date.isoformat(), "disabled": disabled}


def get_bookable_room(room_id: int) -> Room:
    room = db.session.get(Room, room_id)
    if room is None or room.status != STATUS_ACTIVE:
        raise NotFoundError("Room not found.")
    return room


def create_booking(user, room_id: int, payload: dict) -> Booking:
    """Validate + tạo yêu cầu đặt phòng (status pending) cho `user` hiện tại.

    Số khách không nhập: loại phòng đã quy định (A1 = 1 người, B4 = 4 người...).
    Raise ValidationError nếu dữ liệu sai hoặc hết phòng trong khoảng ngày đó.
    """
    room = get_bookable_room(room_id)
    data = _validate_booking_payload(payload)

    booked = _units_booked(room.id, data["check_in"], data["check_out"])
    if booked >= room.total_units:
        raise ValidationError({"_": "These dates are already taken. Please choose different dates."})

    nights = (data["check_out"] - data["check_in"]).days
    total_price = (Decimal(room.price_per_night) * nights).quantize(Decimal("0.01"))

    booking = Booking(
        user_id=user.id,
        room_id=room.id,
        customer_name=data["customer_name"],
        phone=data["phone"],
        special_requests=data["special_requests"],
        check_in=data["check_in"],
        check_out=data["check_out"],
        total_price=total_price,
        status=STATUS_PENDING,  # chờ admin xem xét / tư vấn rồi mới xác nhận
    )
    db.session.add(booking)
    db.session.commit()
    return booking


def list_all_bookings():
    """Tất cả yêu cầu đặt phòng (mới nhất trước) cho Dashboard của admin."""
    stmt = db.select(Booking).where(Booking.status != STATUS_CANCELLED).order_by(Booking.id.desc())
    return list(db.session.scalars(stmt))


def admin_set_status(booking_id: int, status: str) -> Booking:
    """Admin xác nhận (confirmed) hoặc huỷ (cancelled) một yêu cầu đặt phòng.

    Chỉ booking confirmed mới chặn ngày, nên lúc confirm phải kiểm tra lại: nếu khoảng ngày đó
    đã đủ booking confirmed khác thì không confirm được. Khoá hàng của phòng (FOR UPDATE) để
    hai admin confirm cùng lúc không thể vượt quá total_units.
    """
    if status not in (STATUS_CONFIRMED, STATUS_CANCELLED):
        raise ValidationError({"status": "Status must be confirmed or cancelled."})
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        raise NotFoundError("Booking not found.")

    if status == STATUS_CONFIRMED and booking.status != STATUS_CONFIRMED:
        if booking.status == STATUS_CANCELLED:
            raise ValidationError({"_": "This booking was cancelled, so it cannot be confirmed."})
        room = db.session.get(Room, booking.room_id, with_for_update=True)
        taken = _units_booked(room.id, booking.check_in, booking.check_out, exclude_booking_id=booking.id)
        if taken >= room.total_units:
            db.session.rollback()
            raise ValidationError(
                {"_": "These dates are already taken by a confirmed booking. Cancel this request or ask the guest to pick other dates."}
            )

    booking.status = status
    db.session.commit()
    return booking


def list_user_bookings(user):
    stmt = (
        db.select(Booking)
        .where(Booking.user_id == user.id, Booking.status != STATUS_CANCELLED)
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