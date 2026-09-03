# Blue Lotus T-Shirt Creator

An iPad-friendly Flask application for Blue Lotus Temple volunteers to select an approved dog-monk design, preview the front and back of the garment, choose color and size, approve the design, and prepare the verified artwork and order data needed for a future Printful API request.

The current version deliberately stops before Printful. It does not submit orders, store payment information, or create charges.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
flask --app app run
```

Open `http://127.0.0.1:5000`.

## Production boundary

The app currently provides:

- approved breed, design, garment color, size, and quantity selection;
- front/back garment preview;
- design approval reset whenever production choices change;
- U.S. shipping-field validation;
- exact 2,700 × 3,450 transparent PNG output with 300 DPI metadata;
- a structured preview of the future Printful order payload;
- clear disclosure that the current 1,111 × 1,415 mockup source needs a higher-resolution approved master before live fulfillment.

The next phase will add Printful authentication, catalog variant mapping, cost and shipping estimates, draft-order creation, explicit payment approval, and webhook status updates.

The root `index.html` remains the public GitHub Pages mockup. Render runs the Flask application through `app.py` and `render.yaml`.
