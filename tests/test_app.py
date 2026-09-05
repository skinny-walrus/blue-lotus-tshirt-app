from pathlib import Path

from PIL import Image

from app import ARTWORKS, create_app


def make_client(tmp_path: Path, **config):
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "EXPORT_DIR": tmp_path / "exports", "ORDER_DATABASE": tmp_path / "orders.sqlite3", **config})
    return app.test_client()


def csrf(client):
    return client.get("/api/config").get_json()["csrf_token"]


def item(breed="Jagdterrier", **values):
    return {"breed": breed, "color": "Pepper", "size": "M", "quantity": 1, **values}


def test_storefront_and_health(tmp_path):
    client = make_client(tmp_path)
    page = client.get("/")
    assert page.status_code == 200
    for text in (b"Add to cart", b"Secure checkout", b"Pinch-to-zoom", b"Pit Bull", b"German Shepherd", b"Bay", b"Navy"):
        assert text in page.data
    assert b"share love, compassion, and kindness throughout the world" in page.data
    assert b"Wear the dog who taught you how" in page.data
    assert b"all profits support its work teaching meditation and loving kindness" in page.data
    assert b"$29.95" in page.data
    assert b"moss-shirt-back.png" not in page.data
    assert b"useMoss" not in page.data
    assert b"hue-rotate(198deg)" in page.data
    assert b"brightness(2.25)" in page.data
    assert b".shirt.front .garment{left:-7%;clip-path:inset(0 50% 0 0)}" in page.data
    assert b".front-art{position:absolute;width:30%;left:50%" in page.data
    assert b"color==='Ivory'?'brightness(0) opacity(.78)'" in page.data
    assert b"Coming soon" not in page.data
    assert client.get("/api/health").get_json() == {"ok": True, "service": "blue-lotus-tshirt-store", "checkout_configured": False, "printful_connected": False}


def test_all_artwork_is_production_ready():
    for filename in ARTWORKS.values():
        with Image.open(Path("static") / filename) as image:
            assert image.width >= 2700 and image.height >= 3450
            assert image.mode == "RGBA"
            assert image.getextrema()[3] != (255, 255)


def test_checkout_is_guarded_without_credentials(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/api/checkout", json={"items": [item()]}, headers={"X-CSRF-Token": csrf(client)})
    assert response.status_code == 503
    assert response.get_json()["error"] == "Secure checkout is being connected. No payment was taken."
    assert response.get_json()["order_id"]


def test_test_checkout_persists_cart_and_order_page(tmp_path):
    client = make_client(tmp_path, CHECKOUT_TEST_MODE=True)
    payload = {"items": [item(), item("Pit Bull", color="Moss", size="2XL", quantity=2)]}
    response = client.post("/api/checkout", json=payload, headers={"X-CSRF-Token": csrf(client)})
    assert response.status_code == 200
    order = client.get(response.get_json()["checkout_url"])
    assert order.status_code == 200
    assert b"Jagdterrier Tee" in order.data and b"Pit Bull Tee" in order.data and b"$95.85" in order.data


def test_checkout_validation_and_csrf(tmp_path):
    client = make_client(tmp_path)
    assert client.post("/api/checkout", json={"items": [item()]}).status_code == 403
    bad = client.post("/api/checkout", json={"items": [item(color="Chartreuse")]}, headers={"X-CSRF-Token": csrf(client)})
    assert bad.status_code == 400


def test_policy_pages(tmp_path):
    client = make_client(tmp_path)
    for name in ("shipping", "returns", "privacy", "terms"):
        assert client.get(f"/policies/{name}").status_code == 200


def test_staff_print_file_is_verified(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/api/prepare", json=item() | {"approved": True}, headers={"X-CSRF-Token": csrf(client)})
    assert response.status_code == 200
    data = response.get_json()
    assert data["verification"]["pixels"] == [2700, 3450]
    assert data["verification"]["dpi"] == [300, 300]
    assert client.get(data["download_url"]).status_code == 200
