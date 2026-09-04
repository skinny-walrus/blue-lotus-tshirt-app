# Blue Lotus Kindness Collection

An iPad-friendly direct-to-consumer Flask storefront for Blue Lotus Temple's breed-specific Choose Loving Kindness shirts.

## Customer experience

- ten selectable dog breeds with approved transparent artwork;
- Comfort Colors 1717 color, size, and quantity selection;
- realistic front and back shirt previews;
- full-screen detail viewer with buttons, touch panning, and pinch zoom;
- persistent browser shopping cart and server-authoritative pricing;
- Stripe-hosted checkout boundary with U.S. shipping-address collection, promotion codes, and optional automatic tax;
- customer order-status, shipping, returns, privacy, and terms pages;
- webhook-driven Printful fulfillment boundary and shipment tracking.

The launch price is configured in `app.py` as $34.95, with a $3.00 2XL surcharge. The app never trusts a price sent by the browser.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
flask --app app run
```

Open `http://127.0.0.1:5000`.

## Live commerce configuration

Store secrets in the hosting environment, never in Git:

- `FLASK_SECRET_KEY`
- `ORDER_DATABASE`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_AUTOMATIC_TAX` (`true` or `false`)
- `PRINTFUL_TOKEN`
- `PRINTFUL_STORE_ID` when required
- `PRINTFUL_WEBHOOK_TOKEN`
- `PRINTFUL_VARIANT_IDS`, a JSON map such as `{"Pepper|M": 123456}`

Until both Stripe secrets are present, the storefront remains safe to demonstrate: checkout returns a clear setup message and takes no payment. Printful submission occurs only after Stripe sends a verified `checkout.session.completed` event. The customer pays Blue Lotus through Stripe; Printful separately charges Blue Lotus for production and shipping.

Use a persistent location for `ORDER_DATABASE` on PythonAnywhere, for example `/home/skinnywalrus/blue-lotus-data/orders.sqlite3`.
