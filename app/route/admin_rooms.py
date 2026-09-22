"""route/admin_rooms.py — Trang HTML "Edit room" cho admin.

Route chỉ trả về giao diện quản lý phòng.
Dữ liệu được rooms.js tải và thay đổi thông qua API /api/rooms.
"""
from flask import Blueprint, render_template

from app.models.room import ROOM_STATUSES, ROOM_TYPES
from app.utils.decorators import admin_required

bp = Blueprint("admin_rooms", __name__, url_prefix="/admin/rooms")


@bp.get("")
@admin_required
def index():
    """Trang quản lý phòng: bảng danh sách + form thêm/sửa."""
    return render_template("admin/rooms.html", room_types=ROOM_TYPES, room_statuses=ROOM_STATUSES)
