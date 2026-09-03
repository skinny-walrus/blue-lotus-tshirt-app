from __future__ import annotations

import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, render_template, request, send_file, session
from PIL import Image


BASE_DIR = Path(__file__).resolve().parent
TARGET_PIXELS = (2700, 3450)
TARGET_DPI = 300
PRINT_WIDTH_IN = 9
PRINT_HEIGHT_IN = 11.5

COLORS = {
    "Pepper": {"hex": "#5d5d59", "filter": "grayscale(1) brightness(.82) contrast(.92)"},
    "Black": {"hex": "#171817", "filter": "grayscale(1) brightness(.3) contrast(1.12)"},
    "Moss": {"hex": "#68705b", "filter": "grayscale(.35) sepia(.72) hue-rotate(38deg) saturate(.72) brightness(.68)"},
    "Ivory": {"hex": "#ebe3cf", "filter": "grayscale(1) sepia(.28) saturate(.58) brightness(1.72) contrast(.62)"},
}
SIZES = ("S", "M", "L", "XL", "2XL")
BREEDS = (
    "Jagdterrier",
    "French Bulldog",
    "Labrador Retriever",
    "Golden Retriever",
    "German Shepherd Dog",
    "Dachshund",
    "Poodle",
    "Beagle",
    "Rottweiler",
    "German Shorthaired Pointer",
    "Bulldog",
)


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
        MAX_CONTENT_LENGTH=64 * 1024,
        EXPORT_DIR=Path(os.environ.get("EXPORT_DIR", "/tmp/blue-lotus-exports")),
        PRINTFUL_CONNECTED=False,
    )
    if test_config:
        app.config.update(test_config)

    export_dir = Path(app.config["EXPORT_DIR"])
    export_dir.mkdir(parents=True, exist_ok=True)
    prepared_orders: dict[str, dict[str, Any]] = {}

    def csrf_token() -> str:
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(24)
        return session["csrf_token"]

    @app.before_request
    def protect_api() -> None:
        if request.method == "POST" and request.path.startswith("/api/"):
            if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), csrf_token()):
                abort(403, description="The page security token is missing or expired. Refresh and try again.")

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def api_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": getattr(error, "description", "Request failed")}), error.code
        return error

    @app.get("/")
    def home():
        return render_template(
            "app.html",
            breeds=BREEDS,
            colors=COLORS,
            sizes=SIZES,
            csrf_token=csrf_token(),
        )

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "service": "blue-lotus-tshirt-app", "printful_connected": False})

    @app.get("/api/config")
    def config():
        return jsonify(
            {
                "ok": True,
                "breeds": [{"name": name, "available": name == "Jagdterrier"} for name in BREEDS],
                "colors": [{"name": name, **details} for name, details in COLORS.items()],
                "sizes": SIZES,
                "production": {
                    "width_inches": PRINT_WIDTH_IN,
                    "height_inches": PRINT_HEIGHT_IN,
                    "dpi": TARGET_DPI,
                    "pixels": TARGET_PIXELS,
                    "transparent_png": True,
                },
                "printful_connected": False,
                "csrf_token": csrf_token(),
            }
        )

    @app.post("/api/drafts")
    def create_draft():
        payload = _json_payload()
        selection = _validate_selection(payload)
        source = _inspect_source(BASE_DIR / "static" / "jagdterrier-loving-kindness.png")
        return jsonify(
            {
                "ok": True,
                "draft_id": str(uuid.uuid4()),
                "selection": selection,
                "production_check": source,
                "message": "Draft validated. No Printful order or charge was created.",
            }
        )

    @app.post("/api/prepare")
    def prepare_order():
        payload = _json_payload()
        selection = _validate_selection(payload)
        if payload.get("approved") is not True:
            abort(400, description="Approve the design before preparing the order package.")
        recipient = _validate_recipient(payload.get("recipient"))

        draft_id = str(uuid.uuid4())
        filename = f"blue-lotus-jagdterrier-{selection['color'].lower()}-{selection['size'].lower()}-{draft_id[:8]}.png"
        output_path = export_dir / filename
        verification = _prepare_print_file(
            BASE_DIR / "static" / "jagdterrier-loving-kindness.png",
            output_path,
        )
        handoff = _build_printful_handoff(selection, recipient, draft_id)
        prepared_orders[draft_id] = {
            "created_at": time.time(),
            "path": output_path,
            "filename": filename,
            "handoff": handoff,
        }
        _prune_prepared(prepared_orders)

        return jsonify(
            {
                "ok": True,
                "draft_id": draft_id,
                "status": "ready_for_printful_connection",
                "download_url": f"/api/print-file/{draft_id}",
                "verification": verification,
                "printful_handoff": handoff,
                "message": "Order package prepared. Nothing was sent to Printful and no charge was created.",
            }
        )

    @app.get("/api/print-file/<draft_id>")
    def download_print_file(draft_id: str):
        prepared = prepared_orders.get(draft_id)
        if not prepared or not Path(prepared["path"]).is_file():
            abort(404, description="That prepared file is no longer available. Prepare it again.")
        return send_file(
            prepared["path"],
            mimetype="image/png",
            as_attachment=True,
            download_name=prepared["filename"],
        )

    return app


def _json_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400, description="A JSON request body is required.")
    return payload


def _validate_selection(payload: dict[str, Any]) -> dict[str, Any]:
    breed = str(payload.get("breed", "")).strip()
    color = str(payload.get("color", "")).strip()
    size = str(payload.get("size", "")).strip()
    try:
        quantity = int(payload.get("quantity", 1))
    except (TypeError, ValueError):
        abort(400, description="Quantity must be a whole number.")

    if breed not in BREEDS:
        abort(400, description="Choose a listed dog breed.")
    if breed != "Jagdterrier":
        abort(400, description=f"{breed} artwork is still coming soon.")
    if color not in COLORS:
        abort(400, description="Choose an available garment color.")
    if size not in SIZES:
        abort(400, description="Choose an available garment size.")
    if not 1 <= quantity <= 10:
        abort(400, description="Quantity must be between 1 and 10.")

    return {
        "breed": breed,
        "design": "Choose Loving Kindness",
        "garment": "Comfort Colors 1717",
        "color": color,
        "size": size,
        "quantity": quantity,
        "front": "Jagdterrier large artwork",
        "back": "Blue Lotus logo below collar",
    }


def _validate_recipient(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        abort(400, description="Enter the shipping information before preparing the order package.")
    fields = {
        "name": "recipient name",
        "address1": "street address",
        "city": "city",
        "state_code": "state",
        "zip": "ZIP code",
        "country_code": "country",
        "email": "email address",
    }
    recipient: dict[str, str] = {}
    for key, label in fields.items():
        text = str(value.get(key, "")).strip()
        if not text:
            abort(400, description=f"Enter the {label}.")
        if len(text) > 120:
            abort(400, description=f"The {label} is too long.")
        recipient[key] = text
    if recipient["country_code"].upper() != "US":
        abort(400, description="This first version supports U.S. shipping addresses only.")
    recipient["country_code"] = "US"
    recipient["state_code"] = recipient["state_code"].upper()
    return recipient


def _inspect_source(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        width, height = image.size
        has_alpha = image.mode in ("RGBA", "LA") or "transparency" in image.info
    effective_dpi = round(min(width / PRINT_WIDTH_IN, height / PRINT_HEIGHT_IN), 1)
    return {
        "source_pixels": [width, height],
        "source_has_transparency": has_alpha,
        "effective_dpi_at_target_size": effective_dpi,
        "target_pixels": list(TARGET_PIXELS),
        "target_dpi": TARGET_DPI,
        "ready_without_upscaling": width >= TARGET_PIXELS[0] and height >= TARGET_PIXELS[1],
        "warning": None
        if width >= TARGET_PIXELS[0] and height >= TARGET_PIXELS[1]
        else "The approved mockup artwork is smaller than the 300 DPI production target and must be upscaled.",
    }


def _prepare_print_file(source_path: Path, output_path: Path) -> dict[str, Any]:
    with Image.open(source_path) as source:
        source = source.convert("RGBA")
        source_width, source_height = source.size
        scale = min(TARGET_PIXELS[0] / source_width, TARGET_PIXELS[1] / source_height)
        resized_size = (round(source_width * scale), round(source_height * scale))
        resized = source.resize(resized_size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", TARGET_PIXELS, (0, 0, 0, 0))
        canvas.alpha_composite(
            resized,
            ((TARGET_PIXELS[0] - resized.width) // 2, (TARGET_PIXELS[1] - resized.height) // 2),
        )
        canvas.save(output_path, format="PNG", dpi=(TARGET_DPI, TARGET_DPI), optimize=True)

    with Image.open(output_path) as verified:
        dpi = verified.info.get("dpi", (0, 0))
        alpha_extrema = verified.getchannel("A").getextrema()
        return {
            "pixels": list(verified.size),
            "mode": verified.mode,
            "dpi": [round(float(dpi[0])), round(float(dpi[1]))],
            "transparent_alpha": alpha_extrema[0] < 255,
            "exact_approved_artwork_preserved": True,
            "upscaled": source_width < TARGET_PIXELS[0] or source_height < TARGET_PIXELS[1],
            "source_pixels": [source_width, source_height],
        }


def _build_printful_handoff(selection: dict[str, Any], recipient: dict[str, str], draft_id: str) -> dict[str, Any]:
    return {
        "external_id": f"blue-lotus-{draft_id}",
        "recipient": recipient,
        "item": {
            "product_name": selection["garment"],
            "color": selection["color"],
            "size": selection["size"],
            "quantity": selection["quantity"],
            "front_placement": "front",
            "back_placement": "back",
        },
        "pending_printful_fields": [
            "catalog_variant_id",
            "public front print-file URL",
            "public back-logo URL",
            "Printful API credential",
        ],
        "submit_to_printful": False,
    }


def _prune_prepared(prepared_orders: dict[str, dict[str, Any]]) -> None:
    cutoff = time.time() - 60 * 60
    for draft_id, prepared in list(prepared_orders.items()):
        if prepared["created_at"] < cutoff:
            Path(prepared["path"]).unlink(missing_ok=True)
            prepared_orders.pop(draft_id, None)


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
