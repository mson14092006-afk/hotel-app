"""test_rooms.py — Test Room CRUD (API + phân quyền + đăng nhập)."""

VALID = {
    "name": "Deluxe Twin",
    "type": "twin",
    "capacity": 2,
    "total_units": 5,
    "price_per_night": "1200000",
    "status": "active",
    "description": "Two single beds",
}


def create(client, **overrides):
    return client.post("/api/rooms", json={**VALID, **overrides})


# ---------------------------------------------------------------- Phân quyền
def test_api_requires_login(client):
    assert client.get("/api/rooms").status_code == 401
    assert create(client).status_code == 401


def test_api_rejects_non_admin(customer_client):
    assert customer_client.get("/api/rooms").status_code == 403


def test_admin_page_redirects_to_login(client):
    response = client.get("/admin/rooms")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_wrong_password(client, admin_client):
    other = client.post("/login", data={"username": "admin", "password": "nope"})
    assert other.status_code == 401


def test_login_blocks_open_redirect(app):
    from app.models.user import ROLE_ADMIN
    from tests.conftest import _make_user

    _make_user("boss", ROLE_ADMIN)
    response = app.test_client().post(
        "/login?next=//evil.com", data={"username": "boss", "password": "password123"}
    )
    assert "evil.com" not in response.headers["Location"]


# ---------------------------------------------------------------------- Create
def test_create_room(admin_client):
    response = create(admin_client)
    assert response.status_code == 201
    body = response.get_json()
    assert body["id"] == 1
    assert body["price_per_night"] == "1200000.00"
    assert body["status"] == "active"


def test_create_defaults_status_and_nulls_blank_description(admin_client):
    payload = {k: v for k, v in VALID.items() if k != "status"}
    payload["description"] = "   "
    body = admin_client.post("/api/rooms", json=payload).get_json()
    assert body["status"] == "active"
    assert body["description"] is None


def test_create_validation_errors(admin_client):
    response = admin_client.post(
        "/api/rooms",
        json={"name": " ", "type": "castle", "capacity": 0, "total_units": "x",
              "price_per_night": -5, "status": "??"},
    )
    assert response.status_code == 422
    fields = response.get_json()["fields"]
    assert set(fields) == {"name", "type", "capacity", "total_units", "price_per_night", "status"}


def test_create_rejects_bad_types(admin_client):
    assert create(admin_client, capacity=True).status_code == 422
    assert create(admin_client, capacity=2.5).status_code == 422
    assert create(admin_client, price_per_night="NaN").status_code == 422
    assert create(admin_client, price_per_night="1e20").status_code == 422
    assert admin_client.post("/api/rooms", data="not json").status_code == 422


def test_create_duplicate_name(admin_client):
    assert create(admin_client).status_code == 201
    response = create(admin_client)
    assert response.status_code == 409
    assert "name" in response.get_json()["fields"]


# ------------------------------------------------------------------- Read/List
def test_list_and_filters(admin_client):
    create(admin_client, name="Deluxe Twin", type="twin")
    create(admin_client, name="Family 100%", type="family", status="maintenance")
    create(admin_client, name="Suite Lake", type="suite")

    assert admin_client.get("/api/rooms").get_json()["count"] == 3
    assert admin_client.get("/api/rooms?q=lake").get_json()["count"] == 1
    assert admin_client.get("/api/rooms?type=family").get_json()["count"] == 1
    assert admin_client.get("/api/rooms?status=maintenance").get_json()["count"] == 1
    # '%' do người dùng gõ được coi là ký tự thường, không phải wildcard
    assert admin_client.get("/api/rooms?q=%25").get_json()["count"] == 1
    assert admin_client.get("/api/rooms?status=bogus").status_code == 422


def test_get_room_and_404(admin_client):
    room_id = create(admin_client).get_json()["id"]
    assert admin_client.get(f"/api/rooms/{room_id}").status_code == 200
    response = admin_client.get("/api/rooms/999")
    assert response.status_code == 404
    assert response.get_json()["error"]


# ---------------------------------------------------------------------- Update
def test_update_room(admin_client):
    room_id = create(admin_client, status="maintenance").get_json()["id"]
    payload = {k: v for k, v in VALID.items() if k != "status"}
    payload.update(name="Deluxe Twin Plus", price_per_night="1350000.50")

    response = admin_client.put(f"/api/rooms/{room_id}", json=payload)
    body = response.get_json()
    assert response.status_code == 200
    assert body["name"] == "Deluxe Twin Plus"
    assert body["price_per_night"] == "1350000.50"
    assert body["status"] == "maintenance"  # thiếu status -> giữ nguyên


def test_update_to_duplicate_name(admin_client):
    create(admin_client, name="A")
    room_b = create(admin_client, name="B").get_json()["id"]
    response = admin_client.put(f"/api/rooms/{room_b}", json={**VALID, "name": "A"})
    assert response.status_code == 409


def test_update_missing_room(admin_client):
    assert admin_client.put("/api/rooms/999", json=VALID).status_code == 404


# ---------------------------------------------------------------------- Delete
def test_delete_room(admin_client):
    room_id = create(admin_client).get_json()["id"]
    assert admin_client.delete(f"/api/rooms/{room_id}").status_code == 204
    assert admin_client.get(f"/api/rooms/{room_id}").status_code == 404
    assert admin_client.delete(f"/api/rooms/{room_id}").status_code == 404


# ------------------------------------------------------------------------ Pages
def test_pages_render(admin_client, client):
    assert client.get("/").status_code == 200
    assert client.get("/login").status_code == 200
    assert admin_client.get("/admin/rooms").status_code == 200
