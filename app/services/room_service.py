"""services/room_service.py — Business logic cho Room: validate + CRUD."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.room import ROOM_STATUSES, ROOM_TYPES, STATUS_ACTIVE, Room
from app.services.errors import ConflictError, NotFoundError, ValidationError

NAME_MAX = 120
DESCRIPTION_MAX = 2000
CAPACITY_MAX = 20
UNITS_MAX = 1000
PRICE_MAX = Decimal("9999999999.99")  # vừa với Numeric(12, 2)


# Validation
def _parse_int(payload: dict, field: str, label: str, maximum: int, errors: dict):
    """Đọc số nguyên trong khoảng [1, maximum]; ghi lỗi vào `errors` nếu sai."""
    value = payload.get(field)
    if value is None or value == "" or isinstance(value, bool):
        errors[field] = f"{label} is required."
        return None
    if isinstance(value, float) and not value.is_integer():
        errors[field] = f"{label} must be a whole number."
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        errors[field] = f"{label} must be a whole number."
        return None
    if not 1 <= number <= maximum:
        errors[field] = f"{label} must be between 1 and {maximum}."
        return None
    return number


def _parse_price(payload: dict, errors: dict):
    """Đọc giá thành Decimal 2 chữ số, > 0 và không vượt PRICE_MAX."""
    value = payload.get("price_per_night")
    if value is None or value == "" or isinstance(value, bool):
        errors["price_per_night"] = "Price per night is required."
        return None
    try:
        price = Decimal(str(value).strip())
    except InvalidOperation:
        errors["price_per_night"] = "Price per night must be a number."
        return None
    if not price.is_finite():
        errors["price_per_night"] = "Price per night must be a number."
        return None
    if price <= 0:
        errors["price_per_night"] = "Price per night must be greater than 0."
        return None
    if price > PRICE_MAX:
        errors["price_per_night"] = "Price per night is too large."
        return None
    return price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_room_payload(payload, default_status: str = STATUS_ACTIVE) -> dict:
    """Kiểm tra + làm sạch dữ liệu phòng. Trả dict sạch hoặc raise ValidationError.

    Chỉ lấy các field nằm trong whitelist (bỏ qua `id` và field lạ) để client
    không ghi đè được thứ nó không được phép.
    """
    if not isinstance(payload, dict):
        raise ValidationError({"_": "Request body must be a JSON object."})

    errors: dict[str, str] = {}
    clean: dict = {}

    # name
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        errors["name"] = "Name is required."
    elif len(name.strip()) > NAME_MAX:
        errors["name"] = f"Name must be at most {NAME_MAX} characters."
    else:
        clean["name"] = name.strip()

    # type
    room_type = payload.get("type")
    if room_type not in ROOM_TYPES:
        errors["type"] = "Type must be one of: " + ", ".join(ROOM_TYPES) + "."
    else:
        clean["type"] = room_type

    # capacity, total_units, price_per_night
    capacity = _parse_int(payload, "capacity", "Capacity", CAPACITY_MAX, errors)
    if capacity is not None:
        clean["capacity"] = capacity
    units = _parse_int(payload, "total_units", "Total units", UNITS_MAX, errors)
    if units is not None:
        clean["total_units"] = units
    price = _parse_price(payload, errors)
    if price is not None:
        clean["price_per_night"] = price

    # status (không bắt buộc: thiếu thì dùng default_status)
    status = payload.get("status", default_status)
    if status is None or status == "":
        status = default_status
    if status not in ROOM_STATUSES:
        errors["status"] = "Status must be one of: " + ", ".join(ROOM_STATUSES) + "."
    else:
        clean["status"] = status

    # description (không bắt buộc, rỗng -> NULL)
    description = payload.get("description")
    if description is None:
        clean["description"] = None
    elif not isinstance(description, str):
        errors["description"] = "Description must be text."
    elif len(description.strip()) > DESCRIPTION_MAX:
        errors["description"] = f"Description must be at most {DESCRIPTION_MAX} characters."
    else:
        clean["description"] = description.strip() or None

    if errors:
        raise ValidationError(errors)
    return clean


# CRUD
def list_rooms(q: str | None = None, status: str | None = None, room_type: str | None = None):
    """Danh sách phòng, lọc tuỳ chọn theo tên (chứa q), status, type."""
    errors = {}
    if status and status not in ROOM_STATUSES:
        errors["status"] = "Unknown status."
    if room_type and room_type not in ROOM_TYPES:
        errors["type"] = "Unknown type."
    if errors:
        raise ValidationError(errors)

    stmt = db.select(Room).order_by(Room.id)
    if q:
        # autoescape: ký tự % và _ do người dùng gõ được coi là chữ thường
        stmt = stmt.where(Room.name.icontains(q.strip(), autoescape=True))
    if status:
        stmt = stmt.where(Room.status == status)
    if room_type:
        stmt = stmt.where(Room.type == room_type)
    return list(db.session.scalars(stmt))


def get_room(room_id: int) -> Room:
    """Lấy một phòng theo id, raise NotFoundError nếu không có."""
    room = db.session.get(Room, room_id)
    if room is None:
        raise NotFoundError("Room not found.")
    return room


def create_room(payload) -> Room:
    """Validate rồi tạo phòng mới."""
    room = Room(**validate_room_payload(payload))
    db.session.add(room)
    _commit()
    return room


def update_room(room_id: int, payload) -> Room:
    """Cập nhật toàn bộ thông tin phòng (PUT). Thiếu `status` thì giữ status hiện tại."""
    room = get_room(room_id)
    for field, value in validate_room_payload(payload, default_status=room.status).items():
        setattr(room, field, value)
    _commit()
    return room


def delete_room(room_id: int) -> None:
    """Xoá phòng.

    Khi có bảng bookings (FK tới rooms, ON DELETE RESTRICT), phòng đã có booking sẽ
    không xoá được: bắt IntegrityError ở _commit và gợi ý chuyển status sang inactive.
    """
    room = get_room(room_id)
    db.session.delete(room)
    _commit()


def _commit() -> None:
    """Commit; dịch lỗi trùng tên của DB thành ConflictError thân thiện.

    Dựa vào UNIQUE constraint ở DB (thay vì check-rồi-insert) nên không bị race
    condition khi hai admin tạo cùng tên một lúc.
    """
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        message = str(exc.orig)
        if "uq_rooms_name" in message or "rooms.name" in message:
            raise ConflictError("A room with this name already exists.", field="name") from exc
        raise
