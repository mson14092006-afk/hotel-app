"""models/room.py —  bảng `rooms`.

Model chỉ mô tả dữ liệu + ràng buộc DB; luật nghiệp vụ nằm ở services/room_service.py.
"""
from decimal import Decimal

from app.extensions import db

ROOM_TYPES = ("single", "double", "twin", "family", "suite")

STATUS_ACTIVE = "active"            # cho phép đặt
STATUS_MAINTENANCE = "maintenance"  # tạm ngưng (sửa chữa)
STATUS_INACTIVE = "inactive"        # ẩn khỏi khách
ROOM_STATUSES = (STATUS_ACTIVE, STATUS_MAINTENANCE, STATUS_INACTIVE)


class Room(db.Model):
    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    type = db.Column(db.String(30), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)     # số khách tối đa / 1 phòng
    total_units = db.Column(db.Integer, nullable=False)  # số phòng vật lý của loại này
    # Numeric (không dùng Float) để tiền không bị sai số làm tròn.
    price_per_night = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(
        db.String(20), nullable=False, default=STATUS_ACTIVE, server_default=STATUS_ACTIVE
    )
    description = db.Column(db.Text, nullable=True)

    # Điều kiện của DB
    __table_args__ = (
        db.CheckConstraint("capacity > 0", name="capacity_positive"),
        db.CheckConstraint("total_units > 0", name="total_units_positive"),
        db.CheckConstraint("price_per_night > 0", name="price_positive"),
        db.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in ROOM_STATUSES) + ")",
            name="status_valid",
        ),
    )

    def to_dict(self) -> dict:
        """Chuyển sang dict JSON-safe. Giá trả về dạng chuỗi để không mất độ chính xác."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "capacity": self.capacity,
            "total_units": self.total_units,
            "price_per_night": str(Decimal(self.price_per_night).quantize(Decimal("0.01"))),
            "status": self.status,
            "description": self.description,
        }

    def __repr__(self) -> str:
        return f"<Room {self.id} {self.name!r}>"
