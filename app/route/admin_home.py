"""route/admin_home.py — Trang đầu của admin ("Hello Admin") tại /admin."""
from flask import Blueprint, render_template

from app.utils.decorators import admin_required

bp = Blueprint("admin_home", __name__, url_prefix="/admin")


@bp.get("")
@admin_required
def index():
    """Trang "Hello Admin". Chưa đăng nhập -> /login, không phải admin -> 403."""
    return render_template("admin/home.html")