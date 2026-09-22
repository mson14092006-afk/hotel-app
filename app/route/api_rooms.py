"""route/api_rooms.py — REST API JSON cho Room CRUD (chỉ admin).
"""
from flask import Blueprint, jsonify, request

from app.services import room_service
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.utils.decorators import admin_required

bp = Blueprint("api_rooms", __name__, url_prefix="/api/rooms")


# Error mapping: Các lỗi được chuyển thành mã HTTP tương ứng -> frontend
@bp.errorhandler(ValidationError)
def handle_validation_error(exc: ValidationError):
    return jsonify(error="Validation failed.", fields=exc.errors), 422


@bp.errorhandler(ConflictError)
def handle_conflict_error(exc: ConflictError):
    fields = {exc.field: exc.message} if exc.field else {}
    return jsonify(error=exc.message, fields=fields), 409


@bp.errorhandler(NotFoundError)
def handle_not_found_error(exc: NotFoundError):
    return jsonify(error=str(exc)), 404


# Routes
@bp.get("")
@admin_required
def list_rooms():
    """Trả danh sách phòng."""
    rooms = room_service.list_rooms(
        q=request.args.get("q"),
        status=request.args.get("status"),
        room_type=request.args.get("type"),
    )
    return jsonify(items=[r.to_dict() for r in rooms], count=len(rooms))


@bp.post("")
@admin_required
def create_room():
    """Tạo phòng mới từ JSON body."""
    room = room_service.create_room(request.get_json(silent=True))
    return jsonify(room.to_dict()), 201


@bp.get("/<int:room_id>")
@admin_required
def get_room(room_id: int):
    """Trả chi tiết một phòng."""
    return jsonify(room_service.get_room(room_id).to_dict())


@bp.put("/<int:room_id>")
@admin_required
def update_room(room_id: int):
    """Cập nhật phòng bằng JSON body."""
    room = room_service.update_room(room_id, request.get_json(silent=True))
    return jsonify(room.to_dict())


@bp.delete("/<int:room_id>")
@admin_required
def delete_room(room_id: int):
    """Xoá phòng."""
    room_service.delete_room(room_id)
    return "", 204
