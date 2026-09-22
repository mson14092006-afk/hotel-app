"""models/user.py — Model User (bảng `users`)."""
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

ROLE_ADMIN = "admin"
ROLE_CUSTOMER = "customer"
USER_ROLES = (ROLE_ADMIN, ROLE_CUSTOMER)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(20), nullable=False, default=ROLE_CUSTOMER, server_default=ROLE_CUSTOMER
    )

    # Chỉ cho phép role thuộc danh sách USER_ROLES.
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
