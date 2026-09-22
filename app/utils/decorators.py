"""Decorator bảo vệ các route admin, kiểm tra đăng nhập và quyền admin."""
from functools import wraps

from flask import abort, g, jsonify, redirect, request, url_for


def admin_required(view):
    """Chỉ cho admin đi tiếp vào `view`."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        is_api = request.path.startswith("/api/")
        # Chưa đăng nhập -> API trả 401 JSON, trang web chuyển tới /login.
        if g.user is None:
            if is_api:
                return jsonify(error="Authentication required."), 401
            return redirect(url_for("auth.login", next=request.path))
        # Đã đăng nhập nhưng không phải admin -> 403
        if not g.user.is_admin:
            abort(403)  # handler chung trả JSON cho /api/*, HTML cho còn lại
        return view(*args, **kwargs)

    return wrapped