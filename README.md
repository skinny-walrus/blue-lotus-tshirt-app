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
- `PRINTFUL_VARIANT_IDS`, a JSON map such as `{"Grey|M": 123456}`

Until both Stripe secrets are present, the storefront remains safe to demonstrate: checkout returns a clear setup message and takes no payment. Printful submission occurs only after Stripe sends a verified `checkout.session.completed` event. The customer pays Blue Lotus through Stripe; Printful separately charges Blue Lotus for production and shipping.

Use a persistent location for `ORDER_DATABASE` on PythonAnywhere, for example `/home/skinnywalrus/blue-lotus-data/orders.sqlite3`.

Gray is the Comfort Colors Grey garment, not Pepper. Configure Gray (or Grey) and Mystic Blue Printful variant IDs for each size; never reuse Pepper IDs for Gray. All back prints use blue-lotus-logo.png.

Gray and Mystic Blue front/back product photos: https://www.oversizedtg.com/products/comfort-colors-1717 (downloaded September 10, 2026).

Ice Blue replaces Navy. Configure Ice Blue Printful variant IDs for all offered sizes. Ice Blue front/back photos: https://www.bigtopshirtshop.com/products/comfort-colors-mens-short-sleeve-crewneck-t-shirt-c1717-ice-blue

## Email-only checkout (current workflow)

`/checkout` collects contact/shipping details and explicit consent. `/api/checkout` validates the cart, recalculates prices, saves the request, and sends a plain-text email to the fixed order manager. It never creates a Stripe session or submits to Printful. SMTP acceptance is not a guarantee of inbox delivery. Failed/uncertain mail is retained as `email_attention` and is not automatically resent. Review these requests before contacting customers or resending.

Google SMTP defaults: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USE_SSL=false` (mandatory STARTTLS), `SMTP_USERNAME=sid.overbey@melerai.com`, `ORDER_EMAIL_FROM=sid.overbey@melerai.com`, `ORDER_EMAIL_TO=sid.overbey@melerai.com`. Set `SMTP_PASSWORD` privately to an eligible Google app password; never commit it. If this address is an alias, configure the actual authorized sending account instead.

Before deployment, set a persistent `FLASK_SECRET_KEY`, `SESSION_COOKIE_SECURE=true`, and enable HTTPS-only hosting. Keep the database and mail credentials outside static/public directories, accessible only to the application owner. Back up the existing database and review personal-data retention. Verify SMTP connectivity and send one explicitly authorized synthetic order to confirm inbox receipt before enabling customer submissions. Google account/admin policy may require another authentication method if app passwords are unavailable.

Testing mocks SMTP; no real customer email is sent by the test suite.
