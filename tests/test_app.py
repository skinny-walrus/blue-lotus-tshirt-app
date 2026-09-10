from pathlib import Path

from PIL import Image

from app import ARTWORKS, BREEDS, INITIAL_BREED, create_app


def make_client(tmp_path: Path, **config):
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "EXPORT_DIR": tmp_path / "exports", "ORDER_DATABASE": tmp_path / "orders.sqlite3", **config})
    return app.test_client()


def csrf(client):
    return client.get("/api/config").get_json()["csrf_token"]


def item(breed="Jagdterrier", **values):
    return {"breed": breed, "color": "Gray", "size": "M", "quantity": 1, **values}


def test_storefront_and_health(tmp_path):
    client = make_client(tmp_path)
    page = client.get("/")
    assert page.status_code == 200
    for text in (b"Add to cart", b"Review order request", b"Pinch-to-zoom", b"Pit Bull", b"German Shepherd", b"Labradoodle", b"Norwich Terrier", b"Rescue Dog", b"Bay", b"Ice Blue"):
        assert text in page.data
    assert BREEDS == tuple(sorted(BREEDS))
    assert INITIAL_BREED == "Rescue Dog"
    assert b'<option selected>Rescue Dog</option>' in page.data
    assert b'Rescue Dog Loving Kindness Tee' in page.data
    assert b'property="og:image" content="http://localhost/static/link-preview.png"' in page.data
    assert b'property="og:image:width" content="1200"' in page.data
    assert b'name="twitter:card" content="summary_large_image"' in page.data
    assert b"Love In Action" in page.data
    assert b"Wear the companion who taught you how" in page.data
    assert b"All profits from this collection support" in page.data
    assert b"$29.95" in page.data
    assert b"moss-shirt-back.png" not in page.data
    assert b"useMoss" not in page.data
    assert b"hue-rotate(198deg)" not in page.data
    assert b"garment-gray-front.jpg" in page.data
    assert b".shirt.front .garment{left:-7%;clip-path:inset(0 50% 0 0)}" in page.data
    assert b".front-art{position:absolute;width:30%;left:50%" in page.data
    assert b"backArt.style.filter='none'" in page.data
    assert b"Coming soon" not in page.data
    assert client.get("/api/health").get_json() == {"ok": True, "service": "blue-lotus-tshirt-store", "checkout_configured": False, "printful_connected": False}


def test_all_artwork_is_production_ready():
    for filename in ARTWORKS.values():
        with Image.open(Path("static") / filename) as image:
            assert image.width >= 2700 and image.height >= 3450
            assert all(round(dpi) >= 300 for dpi in image.info.get("dpi", (0, 0)))
            assert image.mode == "RGBA"
            assert image.getextrema()[3] != (255, 255)


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


def test_navy_is_no_longer_offered(tmp_path):
    client = make_client(tmp_path)
    assert "Navy" not in [color["name"] for color in client.get("/api/config").get_json()["colors"]]
