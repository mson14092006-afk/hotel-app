"""route/main.py — Trang chủ (Home) của khách sạn."""
from flask import Blueprint, render_template

bp = Blueprint("main", __name__)


@bp.get("/")
def home():
    """Hiển thị trang chủ: tiêu đề ở giữa + phần mô tả khách sạn (template để trống)."""
    return render_template("home.html")
