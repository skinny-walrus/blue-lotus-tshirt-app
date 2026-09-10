from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, render_template, request, send_file, session, url_for
from PIL import Image
from order_requests import register_order_requests, mail_ready


BASE_DIR = Path(__file__).resolve().parent
TARGET_PIXELS = (2700, 3450)
TARGET_DPI = 300
PRINT_WIDTH_IN = 9
PRINT_HEIGHT_IN = 11.5
BASE_PRICE_CENTS = 2995
TWO_XL_SURCHARGE_CENTS = 300

COLORS = {
    "Gray": {"hex": "#858580", "image": "garment-gray-front.jpg", "back_image": "garment-gray-back.jpg"},
    "Mystic Blue": {"hex": "#6486bd", "image": "garment-mystic-blue-front.jpg", "back_image": "garment-mystic-blue-back.jpg"},
    "Ice Blue": {"hex": "#7c9da6", "image": "garment-gray-front.jpg", "back_image": "garment-gray-back.jpg"},
    "Moss": {"hex": "#73765f", "image": "garment-moss.png"},
    "Ivory": {"hex": "#e6dcc7", "image": "garment-ivory.png"},
    "Bay": {"hex": "#b8bfab", "image": "garment-bay.png"},
}
SIZES = ("S", "M", "L", "XL", "2XL")
ARTWORKS = {
    "Beagle": "beagle-loving-kindness.png",
    "Boston Terrier": "boston-terrier-loving-kindness.png",
    "Dachshund": "dachshund-loving-kindness.png",
    "Fat Cat Rescue": "fat-cat-rescue-loving-kindness.png",
    "French Bulldog": "french-bulldog-loving-kindness.png",
    "German Shepherd": "german-shepherd-loving-kindness.png",
    "Golden Retriever": "golden-retriever-loving-kindness.png",
    "Jagdterrier": "jagdterrier-loving-kindness.png",
    "Labradoodle": "labradoodle-loving-kindness.png",
    "Labrador Retriever": "labrador-retriever-loving-kindness.png",
    "Lhasa Apso": "lhasa-apso-loving-kindness.png",
    "Norwich Terrier": "norwich-terrier-loving-kindness.png",
    "Pit Bull": "pit-bull-loving-kindness.png",
    "Rescue Dog": "rescue-dog-loving-kindness.png",
    "Rottweiler": "rottweiler-loving-kindness.png",
    "Sinhala Hound": "sinhala-hound-loving-kindness.png",
}
BREEDS = tuple(ARTWORKS)
INITIAL_BREED = "Rescue Dog"
POLICIES = {
    "shipping": ("Shipping", "Each shirt is made to order. Shipping cost and delivery timing will be confirmed with you before your order is accepted."),
    "returns": ("Returns & exchanges", "Because each item is made to order, we replace items that arrive damaged, misprinted, or incorrect. Contact us within 30 days of delivery with your order number and a photo. Size exchanges for correctly fulfilled items are not currently offered."),
    "privacy": ("Privacy", "We use customer contact and shipping details only to process, fulfill, and support orders. Order requests and customer details are stored by the shop and emailed to its order manager for follow-up. We do not collect card or bank details on this website."),
    "terms": ("Terms", "Product previews are representative. Garment-dyed shirts naturally vary slightly in color. Submitting a request does not charge you or confirm an order. Availability, shipping, tax, and payment arrangements will be confirmed with you before the order is accepted."),
}


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
        MAX_CONTENT_LENGTH=64 * 1024,
        EXPORT_DIR=Path(os.environ.get("EXPORT_DIR", "/tmp/blue-lotus-exports")),
        ORDER_DATABASE=Path(os.environ.get("ORDER_DATABASE", BASE_DIR / "instance" / "orders.sqlite3")),
        STRIPE_SECRET_KEY=os.environ.get("STRIPE_SECRET_KEY", ""),
        STRIPE_WEBHOOK_SECRET=os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
        STRIPE_AUTOMATIC_TAX=os.environ.get("STRIPE_AUTOMATIC_TAX", "true").lower() == "true",
        PRINTFUL_TOKEN=os.environ.get("PRINTFUL_TOKEN", ""),
        PRINTFUL_STORE_ID=os.environ.get("PRINTFUL_STORE_ID", ""),
        PRINTFUL_VARIANT_IDS=os.environ.get("PRINTFUL_VARIANT_IDS", "{}"),
        PRINTFUL_WEBHOOK_TOKEN=os.environ.get("PRINTFUL_WEBHOOK_TOKEN", ""),
        CHECKOUT_TEST_MODE=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
        SMTP_HOST=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        SMTP_PORT=int(os.environ.get("SMTP_PORT", "587")),
        SMTP_USE_SSL=os.environ.get("SMTP_USE_SSL", "false").lower() == "true",
        SMTP_USERNAME=os.environ.get("SMTP_USERNAME", "sid.overbey@melerai.com"),
        SMTP_PASSWORD=os.environ.get("SMTP_PASSWORD", ""),
        ORDER_EMAIL_FROM=os.environ.get("ORDER_EMAIL_FROM", "sid.overbey@melerai.com"),
        ORDER_EMAIL_TO=os.environ.get("ORDER_EMAIL_TO", "sid.overbey@melerai.com"),
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["EXPORT_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["ORDER_DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    _init_database(app.config["ORDER_DATABASE"])

    def csrf_token() -> str:
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(24)
        return session["csrf_token"]

    def checkout_ready() -> bool:
        return mail_ready(app)

    @app.before_request
    def protect_api() -> None:
        if request.method == "POST" and request.path.startswith("/api/"):
            supplied = request.headers.get("X-CSRF-Token", "")
            if not secrets.compare_digest(supplied, csrf_token()):
                abort(403, description="The page security token is missing or expired. Refresh and try again.")

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def api_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": getattr(error, "description", "Request failed")}), error.code
        return render_template("policies.html", title="Page not found", body="That page could not be found."), error.code

    @app.get("/")
    def home():
        return render_template(
            "app.html", breeds=BREEDS, artworks=ARTWORKS, colors=COLORS, sizes=SIZES,
            initial_breed=INITIAL_BREED,
            csrf_token=csrf_token(), base_price_cents=BASE_PRICE_CENTS,
            two_xl_surcharge_cents=TWO_XL_SURCHARGE_CENTS, checkout_configured=checkout_ready(),
        )

    @app.get("/api/health")
    def health():
        return jsonify({
            "ok": True, "service": "blue-lotus-tshirt-store",
            "checkout_configured": checkout_ready(),
            "printful_connected": bool(app.config["PRINTFUL_TOKEN"]),
        })

    @app.get("/api/config")
    def config():
        return jsonify({
            "ok": True,
            "breeds": [{"name": name, "artwork": ARTWORKS[name]} for name in BREEDS],
            "colors": [{"name": name, **details} for name, details in COLORS.items()],
            "sizes": SIZES,
            "pricing": {"base_cents": BASE_PRICE_CENTS, "2xl_surcharge_cents": TWO_XL_SURCHARGE_CENTS, "currency": "usd"},
            "checkout_configured": checkout_ready(), "csrf_token": csrf_token(),
        })

    register_order_requests(app, csrf_token, _validate_selection, _price_item, _save_order, _update_order, _get_order, BASE_PRICE_CENTS, TWO_XL_SURCHARGE_CENTS)

    @app.post("/webhooks/stripe")
    def stripe_webhook():
        if not (app.config["STRIPE_SECRET_KEY"] and app.config["STRIPE_WEBHOOK_SECRET"]):
            abort(404)
        try:
            import stripe

            event = stripe.Webhook.construct_event(
                request.get_data(), request.headers.get("Stripe-Signature", ""), app.config["STRIPE_WEBHOOK_SECRET"]
            )
        except Exception:
            return "Invalid webhook", 400
        if event["type"] == "checkout.session.completed":
            checkout = event["data"]["object"]
            order_id = checkout.get("metadata", {}).get("order_id")
            if order_id:
                shipping = checkout.get("shipping_details") or checkout.get("customer_details") or {}
                _update_order(app.config["ORDER_DATABASE"], order_id, "paid", customer=shipping)
                if app.config["PRINTFUL_TOKEN"]:
                    try:
                        printful_id = _submit_printful_order(app, order_id, checkout, shipping)
                        _update_order(app.config["ORDER_DATABASE"], order_id, "submitted_to_printful", printful_id=str(printful_id))
                    except Exception:
                        app.logger.exception("Printful submission failed for %s", order_id)
                        _update_order(app.config["ORDER_DATABASE"], order_id, "fulfillment_attention")
        return "", 204

    @app.post("/webhooks/printful/<token>")
    def printful_webhook(token: str):
        expected = app.config["PRINTFUL_WEBHOOK_TOKEN"]
        if not expected or not hmac.compare_digest(token, expected):
            abort(404)
        event = request.get_json(silent=True) or {}
        data = event.get("data") or {}
        order = data.get("order") or {}
        external_id = order.get("external_id")
        if external_id:
            status = str(event.get("type", "printful_update"))
            tracking = (data.get("shipment") or {}).get("tracking_url")
            _update_order(app.config["ORDER_DATABASE"], external_id, status, tracking_url=tracking)
        return "", 204

    @app.get("/order/<order_id>")
    def order_status(order_id: str):
        order = _get_order(app.config["ORDER_DATABASE"], order_id)
        if not order:
            abort(404)
        if order["status"] in ("request_sent", "sending_request", "email_attention") and order_id not in session.get("request_receipts", []):
            abort(404)
        return render_template("order.html", order=order)

    @app.get("/policies/<name>")
    def policy(name: str):
        if name not in POLICIES:
            abort(404)
        return render_template("policies.html", title=POLICIES[name][0], body=POLICIES[name][1])

    # Kept as a staff-side production check while the public storefront uses checkout.
    @app.post("/api/prepare")
    def prepare_print_file():
        payload = _json_payload()
        selection = _validate_selection(payload)
        if payload.get("approved") is not True:
            abort(400, description="Approve the design before preparing the print file.")
        draft_id = uuid.uuid4().hex
        filename = f"blue-lotus-{selection['breed'].lower().replace(' ', '-')}-{draft_id[:8]}.png"
        output = Path(app.config["EXPORT_DIR"]) / filename
        verification = _prepare_print_file(_artwork_path(selection["breed"]), output)
        return jsonify({"ok": True, "draft_id": draft_id, "verification": verification, "download_url": url_for("staff_print_file", filename=filename)})

    @app.get("/api/print-file/<filename>")
    def staff_print_file(filename: str):
        safe_name = Path(filename).name
        path = Path(app.config["EXPORT_DIR"]) / safe_name
        if not path.is_file():
            abort(404, description="That prepared file is no longer available.")
        return send_file(path, mimetype="image/png", as_attachment=True, download_name=safe_name)

    return app


def _json_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400, description="A JSON request body is required.")
    return payload


def _validate_selection(payload: dict[str, Any]) -> dict[str, Any]:
    breed, color, size = (str(payload.get(key, "")).strip() for key in ("breed", "color", "size"))
    try:
        quantity = int(payload.get("quantity", 1))
    except (TypeError, ValueError):
        abort(400, description="Quantity must be a whole number.")
    if breed not in ARTWORKS:
        abort(400, description="Choose an available dog breed.")
    if color not in COLORS:
        abort(400, description="Choose an available garment color.")
    if size not in SIZES:
        abort(400, description="Choose an available garment size.")
    if not 1 <= quantity <= 10:
        abort(400, description="Quantity must be between 1 and 10.")
    return {"breed": breed, "color": color, "size": size, "quantity": quantity, "design": "Choose Loving Kindness", "garment": "Comfort Colors 1717"}


def _price_item(selection: dict[str, Any]) -> dict[str, Any]:
    unit = BASE_PRICE_CENTS + (TWO_XL_SURCHARGE_CENTS if selection["size"] == "2XL" else 0)
    return {**selection, "unit_price_cents": unit, "line_total_cents": unit * selection["quantity"], "artwork": ARTWORKS[selection["breed"]]}


def _artwork_path(breed: str) -> Path:
    return BASE_DIR / "static" / ARTWORKS[breed]


def _init_database(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            status TEXT NOT NULL, total_cents INTEGER NOT NULL, items_json TEXT NOT NULL,
            stripe_session_id TEXT, printful_id TEXT, customer_json TEXT, tracking_url TEXT
        )""")


def _save_order(path: Path, order_id: str, status: str, items: list[dict[str, Any]], total_cents: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO orders (id, created_at, updated_at, status, total_cents, items_json) VALUES (?, ?, ?, ?, ?, ?)",
                   (order_id, now, now, status, total_cents, json.dumps(items)))


def _update_order(path: Path, order_id: str, status: str, **values: Any) -> None:
    allowed = {"stripe_session_id", "printful_id", "customer", "tracking_url"}
    fields, params = ["status = ?", "updated_at = ?"], [status, datetime.now(timezone.utc).isoformat()]
    for key, value in values.items():
        if key not in allowed:
            continue
        column = "customer_json" if key == "customer" else key
        fields.append(f"{column} = ?")
        params.append(json.dumps(value) if key == "customer" else value)
    params.append(order_id)
    with sqlite3.connect(path) as db:
        db.execute(f"UPDATE orders SET {', '.join(fields)} WHERE id = ?", params)


def _get_order(path: Path, order_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["items"] = json.loads(result.pop("items_json"))
    result["customer"] = json.loads(result.pop("customer_json")) if result.get("customer_json") else None
    result.pop("customer_json", None)
    return result


def _variant_map(app: Flask) -> dict[str, int]:
    try:
        return {str(key): int(value) for key, value in json.loads(app.config["PRINTFUL_VARIANT_IDS"]).items()}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _submit_printful_order(app: Flask, order_id: str, checkout: dict[str, Any], shipping: dict[str, Any]) -> int:
    order = _get_order(app.config["ORDER_DATABASE"], order_id)
    if not order:
        raise ValueError("Order not found")
    address = shipping.get("address") or {}
    variants = _variant_map(app)
    items = []
    for item in order["items"]:
        variant_id = variants.get(f"{item['color']}|{item['size']}")
        if not variant_id and item["color"] == "Gray":
            variant_id = variants.get(f"Grey|{item['size']}")
        if not variant_id:
            raise ValueError(f"Missing Printful variant for {item['color']} {item['size']}")
        items.append({
            "variant_id": variant_id, "quantity": item["quantity"],
            "files": [
                {"type": "front", "url": url_for("static", filename=item["artwork"], _external=True)},
                {"type": "back", "url": url_for("static", filename="blue-lotus-logo.png", _external=True)},
            ],
        })
    payload = {
        "external_id": order_id,
        "recipient": {
            "name": shipping.get("name") or (checkout.get("customer_details") or {}).get("name"),
            "email": (checkout.get("customer_details") or {}).get("email"),
            "address1": address.get("line1"), "address2": address.get("line2"),
            "city": address.get("city"), "state_code": address.get("state"),
            "country_code": address.get("country"), "zip": address.get("postal_code"),
        },
        "items": items,
    }
    headers = {"Authorization": f"Bearer {app.config['PRINTFUL_TOKEN']}", "Content-Type": "application/json"}
    if app.config["PRINTFUL_STORE_ID"]:
        headers["X-PF-Store-Id"] = str(app.config["PRINTFUL_STORE_ID"])
    req = urllib.request.Request("https://api.printful.com/orders?confirm=true", data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode(errors="replace")) from exc
    return int(result["result"]["id"])


def _prepare_print_file(source_path: Path, output_path: Path) -> dict[str, Any]:
    with Image.open(source_path) as source:
        source.load()
        source_rgba = source.convert("RGBA")
        if source_rgba.width < TARGET_PIXELS[0] or source_rgba.height < TARGET_PIXELS[1]:
            raise ValueError(f"{source_path.name} is {source_rgba.size}; production requires at least {TARGET_PIXELS} without upscaling")
        if source_rgba.getextrema()[3] == (255, 255):
            raise ValueError(f"{source_path.name} does not contain transparency")
        if source_rgba.size != TARGET_PIXELS:
            source_rgba.thumbnail(TARGET_PIXELS, Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", TARGET_PIXELS, (0, 0, 0, 0))
            canvas.alpha_composite(source_rgba, ((TARGET_PIXELS[0] - source_rgba.width) // 2, (TARGET_PIXELS[1] - source_rgba.height) // 2))
            source_rgba = canvas
        source_rgba.save(output_path, format="PNG", dpi=(TARGET_DPI, TARGET_DPI), optimize=True)
    with Image.open(output_path) as verified:
        dpi = tuple(round(value) for value in verified.info.get("dpi", (0, 0)))
        digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
        return {"pixels": list(verified.size), "dpi": list(dpi), "transparent_alpha": verified.mode == "RGBA", "upscaled": False, "sha256": digest}


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
