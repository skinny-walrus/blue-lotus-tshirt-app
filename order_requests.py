"""Email-only order requests. No payment or fulfillment is triggered here."""
import hashlib
import hmac
import json
import re
import secrets
import smtplib
import sqlite3
import ssl
import time
from email.message import EmailMessage

from flask import abort, jsonify, render_template, request, session, url_for


US_STATES = {'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'DC': 'District of Columbia', 'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming'}

def mail_ready(app):
    return bool(app.config.get('SMTP_HOST') and app.config.get('ORDER_EMAIL_FROM') and app.config.get('ORDER_EMAIL_TO') and app.config.get('SMTP_USERNAME') and app.config.get('SMTP_PASSWORD'))


def send_order_email(app, order_id, customer, items, total):
    message = EmailMessage()
    message['Subject'] = f'Blue Lotus order request {order_id[:8].upper()}'
    message['From'] = app.config['ORDER_EMAIL_FROM']
    message['To'] = app.config['ORDER_EMAIL_TO']
    message['Reply-To'] = customer['email']
    rows = ['NEW ORDER REQUEST — NO PAYMENT COLLECTED', f'Reference: {order_id}', '', 'CUSTOMER']
    rows += [f'{key.replace("_", " ").title()}: {value}' for key, value in customer.items() if value]
    rows += ['', 'ITEMS']
    rows += [f'{x["quantity"]} × {x["breed"]} | {x["color"]} | {x["size"]} | ${x["line_total_cents"]/100:.2f}' for x in items]
    rows += ['', f'Merchandise subtotal: ${total/100:.2f}', 'Shipping and tax are not included. Contact the customer to confirm availability, final total, and payment arrangements.']
    message.set_content('\n'.join(rows))
    context = ssl.create_default_context()
    if app.config['SMTP_USE_SSL']:
        connection = smtplib.SMTP_SSL(app.config['SMTP_HOST'], app.config['SMTP_PORT'], timeout=20, context=context)
    else:
        connection = smtplib.SMTP(app.config['SMTP_HOST'], app.config['SMTP_PORT'], timeout=20)
    with connection as smtp:
        if not app.config['SMTP_USE_SSL']:
            smtp.starttls(context=context)
        if app.config.get('SMTP_USERNAME'):
            smtp.login(app.config['SMTP_USERNAME'], app.config['SMTP_PASSWORD'])
        if smtp.send_message(message):
            raise smtplib.SMTPException('Recipient refused')


def validate_customer(raw):
    if not isinstance(raw, dict):
        abort(400, description='Enter your contact and shipping details.')
    limits = {'name':120, 'email':254, 'phone':40, 'address1':180, 'address2':180, 'city':100, 'state':100, 'postal_code':20, 'country':2, 'notes':1000}
    customer = {}
    for field, limit in limits.items():
        value = raw.get(field, '')
        if not isinstance(value, str) or len(value) > limit or any(ord(c)<32 and c!='\n' for c in value) or ('\n' in value and field != 'notes'):
            abort(400, description=f'Check the {field.replace("_", " ")} field.')
        customer[field] = value.strip()
    for field in ('name','email','phone','address1','city','state','postal_code','country'):
        if not customer[field]:
            abort(400, description='Complete all required contact and shipping fields.')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', customer['email']):
        abort(400, description='Enter a valid email address.')
    if customer['state'] not in US_STATES:
        abort(400, description='Choose a state from the list.')
    if customer['country'] != 'US':
        abort(400, description='Shipping is currently available within the United States.')
    return customer


def register_order_requests(app, csrf_token, validate_selection, price_item, save_order, update_order, get_order, base_price, surcharge):
    with sqlite3.connect(app.config['ORDER_DATABASE']) as db:
        db.execute('CREATE TABLE IF NOT EXISTS request_throttle (identity TEXT PRIMARY KEY, last_attempt REAL NOT NULL)')

    @app.after_request
    def private_response(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.path.startswith(('/checkout','/order/','/api/')):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/checkout')
    def email_checkout():
        previous = get_order(app.config['ORDER_DATABASE'], session.get('order_request_id', ''))
        if previous and previous['status'] == 'request_sent':
            session.pop('order_request_id', None)
        session.setdefault('order_request_id', secrets.token_hex(16))
        return render_template('checkout.html', csrf_token=csrf_token(), submission_id=session['order_request_id'], email_ready=mail_ready(app), base_price=base_price, surcharge=surcharge, states=US_STATES)

    @app.post('/api/checkout')
    def request_order():
        if not app.testing and not request.is_secure and request.host.split(':')[0] not in ('localhost','127.0.0.1'):
            abort(400, description='Use the HTTPS address to submit your request.')
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400, description='Invalid request.')
        submission = payload.get('submission_id', '')
        if not isinstance(submission, str) or not hmac.compare_digest(submission, session.get('order_request_id','')) or not submission:
            abort(400, description='Refresh the checkout page and try again.')
        previous = get_order(app.config['ORDER_DATABASE'], submission)
        if previous:
            if previous['status'] == 'request_sent':
                return jsonify(ok=True, checkout_url=url_for('order_status', order_id=submission))
            return jsonify(ok=False, error='This request is already recorded. Please contact the shop before submitting again.', reference=submission[:8]), 409
        customer = validate_customer(payload.get('customer'))
        if payload.get('consent') is not True:
            abort(400, description='Confirm that we may use these details to respond to your request.')
        raw_items = payload.get('items')
        if not isinstance(raw_items,list) or not 1<=len(raw_items)<=20 or any(not isinstance(x,dict) for x in raw_items):
            abort(400, description='Your cart must contain between 1 and 20 items.')
        items = [price_item(validate_selection(x)) for x in raw_items]
        if not mail_ready(app):
            return jsonify(ok=False, error='Order requests are not yet available. Your details have not been sent. Please try again later.'), 503
        identity = hmac.new(str(app.secret_key).encode(), (request.remote_addr or 'unknown').encode(), hashlib.sha256).hexdigest()
        now=time.time()
        with sqlite3.connect(app.config['ORDER_DATABASE']) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT last_attempt FROM request_throttle WHERE identity=?',(identity,)).fetchone()
            if row and now-row[0]<60:
                return jsonify(ok=False,error='Please wait a minute before sending another request.'),429
            db.execute('DELETE FROM request_throttle WHERE last_attempt < ?', (now-86400,))
            db.execute('INSERT OR REPLACE INTO request_throttle VALUES (?,?)',(identity,now))
        total=sum(x['line_total_cents'] for x in items)
        try:
            save_order(app.config['ORDER_DATABASE'],submission,'sending_request',items,total)
        except sqlite3.IntegrityError:
            return jsonify(ok=False,error='Your request is already being processed.'),409
        update_order(app.config['ORDER_DATABASE'],submission,'sending_request',customer=customer)
        session['request_receipts'] = (session.get('request_receipts', []) + [submission])[-20:]
        try:
            send_order_email(app,submission,customer,items,total)
        except (smtplib.SMTPException,OSError):
            update_order(app.config['ORDER_DATABASE'],submission,'email_attention')
            app.logger.error('Order email needs attention: %s',submission)
            return jsonify(ok=False,error='We could not confirm email delivery. Your request is saved; please contact the shop with this reference before trying again.',reference=submission[:8]),502
        update_order(app.config['ORDER_DATABASE'],submission,'request_sent')
        return jsonify(ok=True,checkout_url=url_for('order_status',order_id=submission))
