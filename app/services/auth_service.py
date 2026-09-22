"""services/auth_service.py — Đăng ký + xác thực email. """
import re
from urllib.parse import urljoin

from flask import url_for
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.user import ROLE_ADMIN, ROLE_CUSTOMER, User
from app.services import mail_service
from app.services.errors import ConflictError, NotFoundError, ValidationError

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN_LEN = 8
RESEND_COOLDOWN_SECONDS = 60


def _validate_registration(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError({"_": "Invalid form data."})

    errors: dict[str, str] = {}
    clean: dict = {}

    username = (payload.get("username") or "").strip()
    if not USERNAME_RE.match(username):
        errors["username"] = "3-50 characters: letters, numbers, dot, dash or underscore only."
    else:
        clean["username"] = username

    email = (payload.get("email") or "").strip().lower()
    if not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    else:
        clean["email"] = email

    password = payload.get("password") or ""
    confirm = payload.get("confirm_password") or ""
    if len(password) < PASSWORD_MIN_LEN:
        errors["password"] = f"Password must be at least {PASSWORD_MIN_LEN} characters."
    elif password != confirm:
        errors["confirm_password"] = "Passwords do not match."
    else:
        clean["password"] = password

    if errors:
        raise ValidationError(errors)
    return clean


def register_user(payload: dict) -> User:
    """Tạo tài khoản (chưa xác thực) và gửi email xác thực."""
    data = _validate_registration(payload)

    user = User(username=data["username"], email=data["email"], role=ROLE_CUSTOMER)
    user.set_password(data["password"])
    token = user.issue_verification_token()

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        message = str(exc.orig)
        field = "email" if "email" in message else "username"
        raise ConflictError(f"This {field} is already registered.", field=field) from exc

    _send_verification(user, token)
    return user


def _send_verification(user: User, token: str) -> None:
    verify_path = url_for("auth.verify_email", token=token)
    verify_url = urljoin(url_for("main.home", _external=True), verify_path)
    mail_service.send_verification_email(user.email, user.username, verify_url)


def resend_verification(email: str) -> None:
    """Gửi lại email xác thực nếu tài khoản tồn tại và chưa xác thực.

    Luôn trả về bình thường dù email không tồn tại (không tiết lộ email nào đã
    đăng ký); chỉ chặn spam bằng cooldown khi tài khoản có thật.
    """
    user = db.session.scalar(db.select(User).where(User.email == email.strip().lower()))
    if user is None or user.email_verified:
        return
    if user.seconds_since_last_send() < RESEND_COOLDOWN_SECONDS:
        raise ConflictError("Please wait a bit before requesting another email.")

    token = user.issue_verification_token()
    db.session.commit()
    _send_verification(user, token)


def verify_email(token: str) -> User:
    """Xác thực token. Gán role=admin nếu đây là tài khoản admin đầu tiên."""
    user = db.session.scalar(db.select(User).where(User.verification_token == token))
    if user is None:
        raise NotFoundError("This verification link is invalid.")
    if user.email_verified:
        return user  # đã xác thực trước đó (vd. bấm link 2 lần) -> coi như thành công
    if user.verification_token_expired():
        raise ConflictError("This verification link has expired. Request a new one.")

    user.email_verified = True
    user.verification_token = None
    has_admin = db.session.scalar(db.select(User.id).where(User.role == ROLE_ADMIN).limit(1))
    if has_admin is None:
        user.role = ROLE_ADMIN
    db.session.commit()
    return user
