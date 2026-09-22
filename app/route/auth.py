"""route/auth.py — Đăng nhập / đăng xuất bằng session cookie.
"""
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from app.extensions import db
from app.models.user import User

bp = Blueprint("auth", __name__)


@bp.before_app_request
def load_current_user():
    """Chạy trước mỗi request để xác định user hiện tại."""
    user_id = session.get("user_id")
    # Có user_id → lấy User từ DB; chưa đăng nhập → g.user = None.
    g.user = db.session.get(User, user_id) if user_id else None


@bp.app_context_processor
def inject_current_user():
    """Đưa user hiện tại sang template (HTML) dưới tên current_user."""
    return {"current_user": g.get("user")}


def _safe_next(target: str | None) -> str | None:
    """Chỉ chấp nhận đường dẫn nội bộ ("/..."), chặn open-redirect như "//evil.com"."""
    if target and target.startswith("/") and not target.startswith(("//", "/\\")):
        return target
    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    """GET: hiện form. POST: kiểm tra tài khoản rồi mở session."""
    if g.user:
        return redirect(url_for("main.home"))

    next_url = _safe_next(request.values.get("next"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.session.scalar(db.select(User).where(User.username == username))

        # Thông báo chung cho cả "sai username" và "sai password" để không lộ tài khoản nào tồn tại.
        if user is None or not user.check_password(password):
            flash("Invalid username or password.", "error")
            return render_template("login.html", next_url=next_url), 401

        session.clear()  # tránh session fixation
        session["user_id"] = user.id
        if next_url:
            return redirect(next_url)
        return redirect(url_for("admin_rooms.index" if user.is_admin else "main.home"))

    return render_template("login.html", next_url=next_url)


@bp.post("/logout")
def logout():
    """Đăng xuất (POST + CSRF token để trang web lạ không ép người dùng đăng xuất)."""
    session.clear()
    return redirect(url_for("main.home"))
