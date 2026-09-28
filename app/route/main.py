"""route/main.py — Trang chủ (Home) của khách sạn."""
from flask import Blueprint, render_template

from flask import g, redirect, url_for

from app.services import booking_service

bp = Blueprint("main", __name__)


@bp.get("/")
def home():
    """Hiển thị trang chủ: tiêu đề ở giữa + phần mô tả khách sạn (template để trống)."""
    if g.user is not None and g.user.is_admin:
        return redirect(url_for("admin_home.index"))

    rooms = booking_service.list_active_rooms()
    return render_template("client/home.html", rooms=rooms)
