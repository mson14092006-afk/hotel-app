"""test_rooms.py — Test Room CRUD (API + phân quyền + đăng nhập)."""

# Admin chỉ gửi quality + type; name (A1, B2...) và capacity được server sinh ra.  # <== MỚI SỬA
VALID = {
    "quality": "B",  
    "type": "double",  
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
    # B (Standard) + double (2 người) -> tên B2, sức chứa 2  
    assert body["name"] == "B2"  # <== MỚI SỬA
    assert body["capacity"] == 2  # <== MỚI SỬA
    assert body["quality_label"] == "Standard"  


def test_name_and_capacity_are_generated_not_taken_from_client(admin_client):  
    body = create(admin_client, quality="A", type="family", name="Hacked", capacity=99).get_json() 
    assert body["name"] == "A4"  
    assert body["capacity"] == 4  
    assert create(admin_client, quality="A", type="single").get_json()["name"] == "A1" 
    assert create(admin_client, quality="B", type="single").get_json()["name"] == "B1"  

def test_create_defaults_status_and_nulls_blank_description(admin_client):
    payload = {k: v for k, v in VALID.items() if k != "status"}
    payload["description"] = "   "
    body = admin_client.post("/api/rooms", json=payload).get_json()
    assert body["status"] == "active"
    assert body["description"] is None


def test_create_validation_errors(admin_client):
    response = admin_client.post(
        "/api/rooms",
        json={"quality": "C", "type": "castle", "total_units": "x",  
              "price_per_night": -5, "status": "??"},
    )
    assert response.status_code == 422
    fields = response.get_json()["fields"]
    assert set(fields) == {"quality", "type", "total_units", "price_per_night", "status"} 


def test_create_rejects_bad_types(admin_client):
    assert create(admin_client, total_units=True).status_code == 422 
    assert create(admin_client, total_units=2.5).status_code == 422  
    assert create(admin_client, type="twin").status_code == 422  # loại cũ không còn hợp lệ  
    assert create(admin_client, price_per_night="NaN").status_code == 422
    assert create(admin_client, price_per_night="1e20").status_code == 422
    assert admin_client.post("/api/rooms", data="not json").status_code == 422


def test_create_duplicate_room_class(admin_client): 
    assert create(admin_client).status_code == 201
    response = create(admin_client)  # cùng quality + type -> cùng tên B2  
    assert response.status_code == 409
    assert "type" in response.get_json()["fields"] 


# ------------------------------------------------------------------- Read/List
def test_list_and_filters(admin_client):
    create(admin_client, quality="B", type="double")                          # B2  
    create(admin_client, quality="B", type="family", status="maintenance")    # B4  
    create(admin_client, quality="A", type="single")                          # A1 

    assert admin_client.get("/api/rooms").get_json()["count"] == 3
    assert admin_client.get("/api/rooms?q=a1").get_json()["count"] == 1  
    assert admin_client.get("/api/rooms?type=family").get_json()["count"] == 1
    assert admin_client.get("/api/rooms?quality=B").get_json()["count"] == 2 
    assert admin_client.get("/api/rooms?quality=A&type=single").get_json()["count"] == 1  
    assert admin_client.get("/api/rooms?status=maintenance").get_json()["count"] == 1
    # '%' do người dùng gõ được coi là ký tự thường, không phải wildcard
    assert admin_client.get("/api/rooms?q=%25").get_json()["count"] == 0  
    assert admin_client.get("/api/rooms?status=bogus").status_code == 422
    assert admin_client.get("/api/rooms?quality=Z").status_code == 422  


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
    payload.update(quality="A", type="family", price_per_night="1350000.50") 

    response = admin_client.put(f"/api/rooms/{room_id}", json=payload)
    body = response.get_json()
    assert response.status_code == 200
    assert body["name"] == "A4"  # đổi quality/type -> tên + sức chứa tự đổi theo 
    assert body["capacity"] == 4 
    assert body["price_per_night"] == "1350000.50"
    assert body["status"] == "maintenance"  # thiếu status -> giữ nguyên


def test_update_to_duplicate_room_class(admin_client):  
    create(admin_client, quality="A", type="single") 
    room_b = create(admin_client, quality="B", type="single").get_json()["id"]  
    response = admin_client.put(f"/api/rooms/{room_b}", json={**VALID, "quality": "A", "type": "single"})  
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
