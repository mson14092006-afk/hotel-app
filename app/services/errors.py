"""services/errors.py — Định nghĩa các lỗi mà room service có thể gặp -> room_service sử dụng"""


class ServiceError(Exception):
    """Lớp cha của mọi lỗi nghiệp vụ."""


class ValidationError(ServiceError):
    """Dữ liệu đầu vào sai. `errors` là dict {tên_field: thông báo}."""

    def __init__(self, errors: dict[str, str]):
        super().__init__("Validation failed")
        self.errors = errors


class ConflictError(ServiceError):
    """Vi phạm ràng buộc duy nhất (vd. trùng tên phòng)."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


class NotFoundError(ServiceError):
    """Không tìm thấy bản ghi."""
