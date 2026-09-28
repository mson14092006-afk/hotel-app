"""models/booking.py — Model Booking (bảng `bookings`)."""
from app.extensions import db

STATUS_PENDING = "pending"      # vừa đặt, chưa xác nhận
STATUS_CONFIRMED = "confirmed"  # đã xác nhận (hiện tại: tự động xác nhận khi đặt)
STATUS_CANCELLED = "cancelled"  # khách/admin huỷ
STATUS_COMPLETED = "completed"  # đã trả phòng (đặt cho tương lai, chưa có luồng set)
BOOKING_STATUSES = (STATUS_PENDING, STATUS_CONFIRMED, STATUS_CANCELLED, STATUS_COMPLETED)

# Các trạng thái vẫn "chiếm phòng" (tính vào số phòng đã đặt khi kiểm tra còn trống)
ACTIVE_BOOKING_STATUSES = (STATUS_PENDING, STATUS_CONFIRMED)


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id"), nullable=False)
    guests = db.Column(db.Integer, nullable=False)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    # Chốt giá tại thời điểm đặt (không tính lại nếu admin đổi price_per_night sau này).
    total_price = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(
        db.String(20), nullable=False, default=STATUS_PENDING, server_default=STATUS_PENDING
    )

    user = db.relationship("User", backref=db.backref("bookings", lazy="dynamic"))
    room = db.relationship("Room", backref=db.backref("bookings", lazy="dynamic"))

    __table_args__ = (
        db.CheckConstraint("guests > 0", name="guests_positive"),
        db.CheckConstraint("check_out > check_in", name="checkout_after_checkin"),
        db.CheckConstraint("total_price > 0", name="total_price_positive"),
        db.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in BOOKING_STATUSES) + ")",
            name="booking_status_valid",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "room_id": self.room_id,
            "room_name": self.room.name if self.room else None,
            "guests": self.guests,
            "check_in": self.check_in.isoformat(),
            "check_out": self.check_out.isoformat(),
            "total_price": str(self.total_price),
            "status": self.status,
        }

    def __repr__(self) -> str:
        return f"<Booking {self.id} room={self.room_id} user={self.user_id}>"
