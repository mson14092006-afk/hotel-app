"""route/customer.py — Trang cho khách hàng: xem phòng + đặt phòng + xem booking của mình."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from app.services import booking_service
from app.services.errors import NotFoundError, ValidationError
from app.utils.decorators import login_required

bp = Blueprint("customer", __name__)


@bp.get("/rooms")
def rooms():
    """Danh sách phòng đang mở bán — xem công khai, không cần đăng nhập."""
    return render_template("client/rooms.html", rooms=booking_service.list_active_rooms())


@bp.get("/rooms/<int:room_id>")
def room_detail(room_id):
    """Chi tiết 1 phòng + form đặt phòng."""
    try:
        room = booking_service.get_bookable_room(room_id)
    except NotFoundError:
        flash("Room not found.", "error")
        return redirect(url_for("customer.rooms"))
    return render_template("client/room_detail.html", room=room)


@bp.post("/rooms/<int:room_id>/book")
@login_required
def book_room(room_id):
    """Tạo booking cho user đang đăng nhập."""
    try:
        room = booking_service.get_bookable_room(room_id)
    except NotFoundError:
        flash("Room not found.", "error")
        return redirect(url_for("customer.rooms"))

    try:
        booking_service.create_booking(g.user, room_id, request.form)
    except ValidationError as exc:
        for message in exc.errors.values():
            flash(message, "error")
        return render_template("client/room_detail.html", room=room, form=request.form), 422

    flash("Booking confirmed.", "success")
    return redirect(url_for("customer.my_bookings"))


@bp.get("/my-bookings")
@login_required
def my_bookings():
    """Danh sách booking của chính user đang đăng nhập."""
    return render_template("client/my_bookings.html", bookings=booking_service.list_user_bookings(g.user))


@bp.post("/my-bookings/<int:booking_id>/cancel")
@login_required
def cancel_booking(booking_id):
    try:
        booking_service.cancel_booking(g.user, booking_id)
        flash("Booking cancelled.", "success")
    except NotFoundError:
        flash("Booking not found.", "error")
    except ValidationError as exc:
        flash(next(iter(exc.errors.values())), "error")
    return redirect(url_for("customer.my_bookings"))
