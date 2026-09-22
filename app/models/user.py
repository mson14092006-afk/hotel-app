"""models/user.py — Model User (bảng `users`)."""
import secrets
from datetime import datetime, timedelta, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

ROLE_ADMIN = "admin"
ROLE_CUSTOMER = "customer"
USER_ROLES = (ROLE_ADMIN, ROLE_CUSTOMER)

VERIFICATION_TOKEN_TTL = timedelta(hours=24)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(20), nullable=False, default=ROLE_CUSTOMER, server_default=ROLE_CUSTOMER
    )

    # --- Xác thực email ---
    email_verified = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    verification_token = db.Column(db.String(64), nullable=True, unique=True)
    verification_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint(
            "role IN (" + ", ".join(f"'{r}'" for r in USER_ROLES) + ")", name="role_valid"
        ),
    )

    def set_password(self, password: str) -> None:
        """Băm mật khẩu trước khi lưu — không bao giờ lưu mật khẩu gốc."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """So khớp mật khẩu người dùng nhập với hash đã lưu."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    def issue_verification_token(self) -> str:
        """Sinh token xác thực email mới (ngẫu nhiên, không đoán được) và lưu thời điểm gửi."""
        self.verification_token = secrets.token_urlsafe(32)
        self.verification_sent_at = datetime.now(timezone.utc)
        return self.verification_token

    def verification_token_expired(self) -> bool:
        if self.verification_sent_at is None:
            return True
        sent_at = self.verification_sent_at
        if sent_at.tzinfo is None:  # SQLite (test) trả về naive datetime
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - sent_at > VERIFICATION_TOKEN_TTL

    def seconds_since_last_send(self) -> float:
        if self.verification_sent_at is None:
            return float("inf")
        sent_at = self.verification_sent_at
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - sent_at).total_seconds()
