"""config.py — Toàn bộ cấu hình ứng dụng, đọc từ biến môi trường.

Tách config khỏi code để đổi môi trường (dev/test/prod) mà không sửa source

"""
import os

# DEVELOPMENT: chạy app local, dùng PostgreSQL local (Docker Compose).
# TESTING: chạy pytest, dùng test database riêng và được reset sau mỗi test.
# PRODUCTION: chạy app thật trên AWS, dùng PostgreSQL trên Amazon RDS.

class BaseConfig:
    """Cấu hình dùng chung cho mọi môi trường."""

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@db:5432/hotel"
    )
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me")

    # Cookie session: JS không đọc được (HttpOnly) và không gửi kèm request cross-site (Lax).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Token CSRF gắn với session, không tự hết hạn sau 1 giờ (trang admin có thể mở lâu).
    WTF_CSRF_TIME_LIMIT = None

    # --- Email xác thực đăng ký ---
    # "smtp": gửi email thật bằng MAIL_SERVER/MAIL_USERNAME/MAIL_PASSWORD ở dưới.
    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "no-reply@ete4hotel.example")

    @classmethod
    def validate(cls) -> None:
        """Hook kiểm tra cấu hình khi khởi động (mặc định không làm gì)."""


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # cookie chỉ đi qua HTTPS

    @classmethod
    def validate(cls) -> None:
        """Từ chối khởi động production nếu quên đặt SECRET_KEY thật."""
        if cls.SECRET_KEY == "dev-only-secret-change-me":
            raise RuntimeError("SECRET_KEY must be set in production.")


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False  # test client không cần token CSRF
    # Mặc định SQLite in-memory cho nhanh; đặt TEST_DATABASE_URL để test trên PostgreSQL thật.
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite://")


CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
