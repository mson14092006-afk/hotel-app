
"""models/room.py — Model Room (bảng `rooms`)."""
from decimal import Decimal
 
from app.extensions import db
 
# Chất lượng phòng: A = VIP, B = Standard (thường)
QUALITY_VIP = "A"
QUALITY_STANDARD = "B"
ROOM_QUALITIES = (QUALITY_VIP, QUALITY_STANDARD)
QUALITY_LABELS = {QUALITY_VIP: "VIP", QUALITY_STANDARD: "Standard"}
 
# Loại phòng -> số khách tối đa (cũng là chữ số trong tên phòng: A1, B2, B4...)
TYPE_CAPACITY = {"single": 1, "double": 2, "family": 4}
ROOM_TYPES = tuple(TYPE_CAPACITY)
 
STATUS_ACTIVE = "active"            # cho phép đặt
STATUS_MAINTENANCE = "maintenance"  # tạm ngưng (sửa chữa)
STATUS_INACTIVE = "inactive"        # ẩn khỏi khách
ROOM_STATUSES = (STATUS_ACTIVE, STATUS_MAINTENANCE, STATUS_INACTIVE)
 
 
def room_code(quality: str, room_type: str) -> str:
    """Tên phòng sinh từ chất lượng + loại: ("A", "single") -> "A1", ("B", "family") -> "B4"."""
    return f"{quality}{TYPE_CAPACITY[room_type]}"
 
 
class Room(db.Model):
    __tablename__ = "rooms"
 
    id = db.Column(db.Integer, primary_key=True)
    # Sinh tự động từ quality + type (xem room_code) — không nhập tay.
    name = db.Column(db.String(120), nullable=False, unique=True)
    quality = db.Column(db.String(1), nullable=False)    # "A" (VIP) | "B" (Standard)
    type = db.Column(db.String(30), nullable=False)      # single | double | family
    capacity = db.Column(db.Integer, nullable=False)     # số khách tối đa — sinh từ type
    total_units = db.Column(db.Integer, nullable=False)  # số phòng vật lý của hạng này
    # Numeric (không dùng Float) để tiền không bị sai số làm tròn.
    price_per_night = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(
        db.String(20), nullable=False, default=STATUS_ACTIVE, server_default=STATUS_ACTIVE
    )
    description = db.Column(db.Text, nullable=True)
 
    # Lớp bảo vệ cuối cùng ở DB: dù code có bug cũng không lưu được dữ liệu vô lý.
    __table_args__ = (
        db.CheckConstraint(
            "quality IN (" + ", ".join(f"'{q}'" for q in ROOM_QUALITIES) + ")",
            name="quality_valid",
        ),
        db.CheckConstraint(
            "type IN (" + ", ".join(f"'{t}'" for t in ROOM_TYPES) + ")",
            name="type_valid",
        ),
        db.CheckConstraint("capacity > 0", name="capacity_positive"),
        db.CheckConstraint("total_units > 0", name="total_units_positive"),
        db.CheckConstraint("price_per_night > 0", name="price_positive"),
        db.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in ROOM_STATUSES) + ")",
            name="status_valid",
        ),
    )
 
    @property
    def quality_label(self) -> str:
        """Nhãn hiển thị cho khách: "VIP" hoặc "Standard"."""
        return QUALITY_LABELS.get(self.quality, self.quality)
 
    def to_dict(self) -> dict:
        """Chuyển sang dict JSON-safe. Giá trả về dạng chuỗi để không mất độ chính xác."""
        return {
            "id": self.id,
            "name": self.name,
            "quality": self.quality,
            "quality_label": self.quality_label,
            "type": self.type,
            "capacity": self.capacity,
            "total_units": self.total_units,
            "price_per_night": str(Decimal(self.price_per_night).quantize(Decimal("0.01"))),
            "status": self.status,
            "description": self.description,
        }
 
    def __repr__(self) -> str:
        return f"<Room {self.id} {self.name!r}>"