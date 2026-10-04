"""route/admin_home.py — Dashboard của admin tại /admin: danh sách yêu cầu đặt phòng + nút Confirm / Cancel."""
from flask import Blueprint, flash, redirect, render_template, url_for

from app.models.booking import STATUS_CANCELLED, STATUS_CONFIRMED
from app.services import booking_service
from app.services.errors import NotFoundError, ValidationError
from app.utils.decorators import admin_required

bp = Blueprint("admin_home", __name__, url_prefix="/admin")


@bp.get("")
@admin_required
def index():
    """Dashboard. Chưa đăng nhập -> /login, không phải admin -> 403."""
    return render_template("admin/home.html", bookings=booking_service.list_all_bookings())


def _set_status(booking_id: int, status: str, done_message: str):
    try:
        booking_service.admin_set_status(booking_id, status)
        flash(done_message, "success")
    except ValidationError as exc:
        flash(" ".join(exc.errors.values()), "error")
    except NotFoundError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_home.index"))


@bp.post("/bookings/<int:booking_id>/confirm")
@admin_required
def confirm_booking(booking_id):
    return _set_status(booking_id, STATUS_CONFIRMED, "Booking confirmed.")


@bp.post("/bookings/<int:booking_id>/cancel")
@admin_required
def cancel_booking(booking_id):
    return _set_status(booking_id, STATUS_CANCELLED, "Booking cancelled and removed from the list.")