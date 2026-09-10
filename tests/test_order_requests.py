import re
import smtplib
import sqlite3
from unittest.mock import patch

from app import create_app


def setup(tmp_path, **config):
    app=create_app({'TESTING':True,'SECRET_KEY':'test','ORDER_DATABASE':tmp_path/'orders.db','EXPORT_DIR':tmp_path/'exports','SMTP_HOST':'smtp.gmail.com','SMTP_USERNAME':'shop@example.com','SMTP_PASSWORD':'test-password','ORDER_EMAIL_FROM':'shop@example.com','ORDER_EMAIL_TO':'owner@example.com',**config})
    client=app.test_client()
    client.get('/checkout')
    token=client.get('/api/config').json['csrf_token']
    with client.session_transaction() as session:
        submission=session['order_request_id']
    payload={'submission_id':submission,'consent':True,'items':[{'breed':'Rescue Dog','color':'Ice Blue','size':'2XL','quantity':2,'unit_price_cents':1}], 'customer':{'name':'Test Customer','email':'test@example.com','phone':'312-555-0100','address1':'123 Test St','city':'Test City','state':'IL','postal_code':'60000','country':'US'}}
    return app,client,payload,{'X-CSRF-Token':token}


def test_email_request_price_idempotency_and_private_confirmation(tmp_path):
    app,client,payload,headers=setup(tmp_path)
    with patch('order_requests.send_order_email') as send:
        response=client.post('/api/checkout',json=payload,headers=headers)
        assert response.status_code==200
        assert send.call_args.args[-1]==6590
        assert client.post('/api/checkout',json=payload,headers=headers).status_code==200
        send.assert_called_once()
    url=response.json['checkout_url']
    page=client.get(url)
    assert b'No payment has been collected' in page.data
    assert page.headers['Cache-Control']=='no-store'
    assert app.test_client().get(url).status_code==404


def test_security_and_validation(tmp_path):
    app,client,payload,headers=setup(tmp_path)
    assert client.post('/api/checkout',json=payload).status_code==403
    for mutation in ({'consent':False},{'items':[None]},{'submission_id':'bad'},{'customer':{'name':'x'}},{'customer':payload['customer']|{'email':'x@example.com\nBcc:bad@example.com'}}):
        assert client.post('/api/checkout',json=payload|mutation,headers=headers).status_code==400
    for color in ('Pepper','Navy'):
        bad=payload|{'items':[payload['items'][0]|{'color':color}]}
        assert client.post('/api/checkout',json=bad,headers=headers).status_code==400


def test_unconfigured_does_not_store_customer(tmp_path):
    app,client,payload,headers=setup(tmp_path,SMTP_PASSWORD='')
    assert client.post('/api/checkout',json=payload,headers=headers).status_code==503
    with sqlite3.connect(app.config['ORDER_DATABASE']) as db:
        assert db.execute('SELECT count(*) FROM orders').fetchone()[0]==0


def test_mail_failure_not_reported_as_success_or_resent(tmp_path):
    app,client,payload,headers=setup(tmp_path)
    with patch('order_requests.send_order_email',side_effect=smtplib.SMTPException('failed')) as send:
        response=client.post('/api/checkout',json=payload,headers=headers)
        assert response.status_code==502
        assert client.post('/api/checkout',json=payload,headers=headers).status_code==409
        send.assert_called_once()


def test_google_transport_and_recipient(tmp_path):
    app,client,payload,headers=setup(tmp_path)
    with patch('order_requests.smtplib.SMTP') as smtp:
        connection=smtp.return_value.__enter__.return_value
        connection.send_message.return_value={}
        response=client.post('/api/checkout',json=payload,headers=headers)
        assert response.status_code==200
        connection.starttls.assert_called_once()
        connection.login.assert_called_once_with('shop@example.com','test-password')
        message=connection.send_message.call_args.args[0]
        assert message['To']=='owner@example.com'
        assert message['Reply-To']=='test@example.com'
        assert 'Ice Blue' in message.get_content()
        assert 'NO PAYMENT COLLECTED' in message.get_content()


def test_throttle(tmp_path):
    app,client,payload,headers=setup(tmp_path)
    with patch('order_requests.send_order_email'):
        assert client.post('/api/checkout',json=payload,headers=headers).status_code==200
        with client.session_transaction() as session:
            session['order_request_id']='a'*32
        payload['submission_id']='a'*32
        assert client.post('/api/checkout',json=payload,headers=headers).status_code==429


def test_required_phone_and_state_selection(tmp_path):
    app, client, payload, headers = setup(tmp_path)
    for fields in ({'phone': ''}, {'state': 'Not a state'}):
        bad = payload | {'customer': payload['customer'] | fields}
        assert client.post('/api/checkout', json=bad, headers=headers).status_code == 400
    page = client.get('/checkout').data
    assert b'Complete your order' in page
    assert b'<option value="IL">Illinois</option>' in page
