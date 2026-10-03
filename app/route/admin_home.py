"""route/admin_home.py — Dashboard của admin tại /admin: danh sách yêu cầu đặt phòng."""
from flask import Blueprint, render_template

from app.services import booking_service
from app.utils.decorators import admin_required

bp = Blueprint("admin_home", __name__, url_prefix="/admin")


@bp.get("")
@admin_required
def index():
    """Dashboard. Chưa đăng nhập -> /login, không phải admin -> 403."""
    return render_template("admin/home.html", bookings=booking_service.list_all_bookings())