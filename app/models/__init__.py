"""models/__init__.py — Gom các model để import một chỗ."""
from app.models.room import Room
from app.models.user import User
from app.models.booking import Booking

__all__ = ["Room", "User","Booking"]