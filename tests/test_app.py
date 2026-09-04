from pathlib import Path

from PIL import Image

from app import create_app


def make_client(tmp_path: Path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "EXPORT_DIR": tmp_path,
        }
    )
    return app.test_client()


def csrf(client) -> str:
    return client.get("/api/config").get_json()["csrf_token"]


def valid_payload(breed="Jagdterrier"):
    return {
        "breed": breed,
        "color": "Pepper",
        "size": "M",
        "quantity": 1,
    }


def test_home_and_health(tmp_path):
    client = make_client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert b"Garment size" in response.data
    assert b"Prepare Printful-ready package" in response.data
    assert b"Boston Terrier" in response.data
    assert b"Red Doberman" in response.data
    assert b"Dachshund" in response.data
    assert b"Navy" in response.data
    assert b"Bay" in response.data
    assert b"#b8bfab" in response.data
    assert b"#fff4d9" in response.data
    assert b"moss-shirt-back.png" in response.data
    assert b"left:-95.7%" in response.data
    assert b"width:14.4%;left:50%" in response.data

    health = client.get("/api/health").get_json()
    assert health == {
        "ok": True,
        "service": "blue-lotus-tshirt-app",
        "printful_connected": False,
    }


def test_draft_validation_and_unavailable_breed(tmp_path):
    client = make_client(tmp_path)
    token = csrf(client)
    expected_ready = {
        "Jagdterrier": False,
        "Boston Terrier": True,
        "Red Doberman": True,
        "Dachshund": False,
    }
    for breed, production_ready in expected_ready.items():
        response = client.post(
            "/api/drafts",
            json=valid_payload(breed),
            headers={"X-CSRF-Token": token},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["selection"]["breed"] == breed
        assert data["production_check"]["source_has_transparency"] is True
        assert data["production_check"]["meaningful_transparency"] is True
        assert data["production_check"]["production_ready"] is production_ready

    unavailable = valid_payload() | {"breed": "Labrador Retriever"}
    response = client.post("/api/drafts", json=unavailable, headers={"X-CSRF-Token": token})
    assert response.status_code == 400
    assert "coming soon" in response.get_json()["error"]


def test_prepare_requires_csrf_and_approval(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/api/prepare", json=valid_payload())
    assert response.status_code == 403

    token = csrf(client)
    response = client.post("/api/prepare", json=valid_payload(), headers={"X-CSRF-Token": token})
    assert response.status_code == 400
    assert "Approve" in response.get_json()["error"]


def test_prepares_verified_png_and_stops_before_printful(tmp_path):
    client = make_client(tmp_path)
    token = csrf(client)
    payload = valid_payload("Red Doberman") | {
        "approved": True,
        "recipient": {
            "name": "Test Recipient",
            "address1": "100 Test Street",
            "city": "Woodstock",
            "state_code": "IL",
            "zip": "60098",
            "country_code": "US",
            "email": "test@example.com",
        },
    }
    response = client.post("/api/prepare", json=payload, headers={"X-CSRF-Token": token})
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ready_for_printful_connection"
    assert data["printful_handoff"]["submit_to_printful"] is False
    assert data["verification"]["pixels"] == [2700, 3450]
    assert data["verification"]["dpi"] == [300, 300]
    assert data["verification"]["transparent_alpha"] is True
    assert data["verification"]["upscaled"] is False
    assert data["printful_handoff"]["item"]["front_placement"] == "front"

    download = client.get(data["download_url"])
    assert download.status_code == 200
    assert download.mimetype == "image/png"
    exported = next(tmp_path.glob("*.png"))
    with Image.open(exported) as image:
        assert image.size == (2700, 3450)
        assert image.mode == "RGBA"
