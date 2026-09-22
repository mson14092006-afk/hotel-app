"""route/auth.py — Đăng ký, xác thực email, đăng nhập / đăng xuất bằng session cookie."""
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from app.extensions import db
from app.models.user import User
from app.services import auth_service
from app.services.errors import ConflictError, NotFoundError, ValidationError

bp = Blueprint("auth", __name__)


@bp.before_app_request
def load_current_user():
    """Chạy trước mọi request: gán g.user (User hoặc None) và cho template dùng qua `current_user`."""
    user_id = session.get("user_id")
    g.user = db.session.get(User, user_id) if user_id else None


@bp.app_context_processor
def inject_current_user():
    """Cho mọi template truy cập biến `current_user`."""
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

        if not user.email_verified:
            flash("Please verify your email before logging in.", "error")
            return render_template("login.html", next_url=next_url, unverified_email=user.email), 401

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


@bp.route("/register", methods=["GET", "POST"])
def register():
    """GET: hiện form đăng ký. POST: tạo tài khoản (chưa xác thực) + gửi email.

    Người đầu tiên xác thực email thành công sẽ tự động là admin (xem
    services/auth_service.py) — không có ô "role" trên form này.
    """
    if g.user:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        try:
            user = auth_service.register_user(request.form)
        except ValidationError as exc:
            return render_template("register.html", errors=exc.errors, form=request.form), 422
        except ConflictError as exc:
            errors = {exc.field: exc.message} if exc.field else {"_": exc.message}
            return render_template("register.html", errors=errors, form=request.form), 409

        return render_template("check_email.html", email=user.email)

    return render_template("register.html", errors={}, form={})


@bp.get("/verify-email/<token>")
def verify_email(token):
    """Bấm từ email: xác thực tài khoản rồi đưa tới trang đăng nhập."""
    try:
        auth_service.verify_email(token)
    except NotFoundError as exc:
        flash(str(exc), "error")
        return redirect(url_for("auth.login"))
    except ConflictError as exc:
        flash(exc.message, "error")
        return render_template("check_email.html", expired_token=token), 409

    flash("Email verified. You can log in now.", "success")
    return redirect(url_for("auth.login"))


@bp.post("/resend-verification")
def resend_verification():
    """Gửi lại email xác thực. Luôn báo cùng một thông báo dù email có tồn tại hay không."""
    email = request.form.get("email", "")
    try:
        auth_service.resend_verification(email)
    except ConflictError as exc:
        flash(exc.message, "error")
        return render_template("check_email.html", email=email), 429

    return render_template("check_email.html", email=email, resent=True)
