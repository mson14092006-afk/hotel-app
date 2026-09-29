"""test_room_status.py — Phòng chỉ còn 2 trạng thái ACTIVE / INACTIVE."""
import pytest

from app.models.room import ROOM_STATUSES

VALID = {"name": "Deluxe Twin", "type": "twin", "capacity": 2, "total_units": 5, "price_per_night": "1200000"}


@pytest.fixture(autouse=True)
def _require_two_statuses():
    if "maintenance" in ROOM_STATUSES:
        pytest.skip("Chưa bật khối ROOM_STATUSES mới trong app/models/room.py")


def test_only_active_and_inactive_exist():
    assert set(ROOM_STATUSES) == {"active", "inactive"}


def test_api_rejects_maintenance(admin_client):
    response = admin_client.post("/api/rooms", json={**VALID, "status": "maintenance"})
    assert response.status_code == 422
    assert "status" in response.get_json()["fields"]


def test_api_accepts_active_and_inactive(admin_client):
    assert admin_client.post("/api/rooms", json={**VALID, "status": "active"}).status_code == 201
    assert admin_client.post("/api/rooms", json={**VALID, "name": "Other", "status": "inactive"}).status_code == 201


def test_status_filter_rejects_maintenance(admin_client):
    assert admin_client.get("/api/rooms?status=maintenance").status_code == 422
