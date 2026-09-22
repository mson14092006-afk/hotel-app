"""config.py — Toàn bộ cấu hình ứng dụng, đọc từ biến môi trường."""
import os

from dotenv import load_dotenv

load_dotenv()  # đọc file .env (nếu có) vào os.environ


class BaseConfig:
    """Cấu hình dùng chung cho mọi môi trường."""

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://hotel:hotel@localhost:5432/hotel_web"
    )
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me")

    # Cookie session: JS không đọc được (HttpOnly) và không gửi kèm request cross-site (Lax).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Token CSRF gắn với session, không tự hết hạn sau 1 giờ (trang admin có thể mở lâu).
    WTF_CSRF_TIME_LIMIT = None

    @classmethod
    def validate(cls) -> None:
        """Hook kiểm tra cấu hình khi khởi động (mặc định không làm gì)."""


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class StagingConfig(BaseConfig):
    """Cấu hình cho môi trường kiểm thử trước production."""

    DEBUG = False
    SESSION_COOKIE_SECURE = True

    @classmethod
    def validate(cls) -> None:
        """Kiểm tra SECRET_KEY trước khi chạy staging."""
        if cls.SECRET_KEY == "dev-only-secret-change-me":
            raise RuntimeError("SECRET_KEY must be set in staging.")


class ProductionConfig(BaseConfig):
    """Cấu hình cho môi trường production."""

    DEBUG = False
    SESSION_COOKIE_SECURE = True

    @classmethod
    def validate(cls) -> None:
        """Từ chối khởi động nếu quên đặt SECRET_KEY thật."""
        if cls.SECRET_KEY == "dev-only-secret-change-me":
            raise RuntimeError("SECRET_KEY must be set in production.")

CONFIGS = {
    "development": DevelopmentConfig,
    "staging": StagingConfig,
    "production": ProductionConfig,
}
