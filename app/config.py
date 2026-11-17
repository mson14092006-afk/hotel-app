"""config.py — Toàn bộ cấu hình ứng dụng, đọc từ biến môi trường.

Tách config khỏi code để đổi môi trường (dev/test/prod) mà không sửa source

"""
import os

# DEVELOPMENT: chạy app local, dùng PostgreSQL local (Docker Compose).
# TESTING: chạy pytest, dùng test database riêng và được reset sau mỗi test.
# PRODUCTION: chạy app thật trên AWS/Render, dùng PostgreSQL (RDS hoặc Render Postgres).

class BaseConfig:
    """Cấu hình dùng chung cho mọi môi trường."""

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@db:5432/hotel"
    )
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me")  # Khóa bí mật Flask dùng để ký và xác minh dữ liệu session (phiên đăng nhập)

    # Cookie session: JS không đọc được (HttpOnly) và không gửi kèm request cross-site (Lax).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Token CSRF gắn với session, không tự hết hạn sau 1 giờ (trang admin có thể mở lâu).
    WTF_CSRF_TIME_LIMIT = None

    # --- Email xác thực đăng ký (gửi qua Brevo HTTP API, cổng 443) ---
    # Render chặn cổng SMTP (25/465/587) nên không dùng SMTP nữa.
    # "brevo": gửi thật qua Brevo. "console": chỉ in ra log (dùng cho test).
    MAIL_BACKEND = os.getenv("MAIL_BACKEND", "brevo")
    BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")            # API key v3 của Brevo
    MAIL_SENDER_EMAIL = os.getenv("MAIL_SENDER_EMAIL", "")    # phải được verify trong Brevo
    MAIL_SENDER_NAME = os.getenv("MAIL_SENDER_NAME", "ET E4 Hotel")

    @classmethod
    def validate(cls) -> None:
        """Hook kiểm tra cấu hình khi khởi động (mặc định không làm gì)."""


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # cookie chỉ đi qua HTTPS
    PREFERRED_URL_SCHEME = "https"  # link xác thực email (url_for _external) dùng https

    @classmethod
    def validate(cls) -> None:
        """Từ chối khởi động production nếu thiếu cấu hình bắt buộc."""
        if cls.SECRET_KEY == "dev-only-secret-change-me":
            raise RuntimeError("SECRET_KEY must be set in production.")
        # Thiếu cấu hình Brevo thì báo ngay lúc khởi động, không đợi tới lúc có người đăng ký
        if cls.MAIL_BACKEND == "brevo" and not (cls.BREVO_API_KEY and cls.MAIL_SENDER_EMAIL):
            raise RuntimeError("BREVO_API_KEY and MAIL_SENDER_EMAIL must be set in production.")


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False  # test client không cần token CSRF
    # Mặc định SQLite in-memory cho nhanh; đặt TEST_DATABASE_URL để test trên PostgreSQL thật.
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite://")
    MAIL_BACKEND = "console"  # test không bao giờ gửi mail thật

CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}