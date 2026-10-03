"""route/admin_rooms.py — Trang HTML "Edit room" cho admin."""
from flask import Blueprint, render_template

from app.models.room import QUALITY_LABELS, ROOM_QUALITIES, ROOM_STATUSES, ROOM_TYPES  # <== MỚI SỬA
from app.utils.decorators import admin_required

bp = Blueprint("admin_rooms", __name__, url_prefix="/admin/rooms")


@bp.get("")
@admin_required
def index():
    """Trang quản lý phòng: bảng danh sách + form thêm/sửa."""
    return render_template(  
        "admin/rooms.html",  
        room_qualities=ROOM_QUALITIES,  
        quality_labels=QUALITY_LABELS,  
        room_types=ROOM_TYPES,  
        room_statuses=ROOM_STATUSES,  
    )  
