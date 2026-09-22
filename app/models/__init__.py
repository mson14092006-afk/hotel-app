"""models/__init__.py — Gom các model để import một chỗ."""
from app.models.room import Room
from app.models.user import User

__all__ = ["Room", "User"]