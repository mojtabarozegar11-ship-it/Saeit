"""Isolated WSGI checkout pilot (not wired into existing MojPlayWin commerce).

Real invoices require an owner-provisioned deposit pool, merchant-only bearer token,
server-sourced USD/TRX rate, and the HTTPS reverse-proxy security contract in README.
The development preview NEVER allocates an invoice or accepts a transaction.
"""
from __future__ import annotations
import html
import io
import json
import os
import re
import secrets
import time
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from wsgiref.simple_server import make_server

from .core import CheckoutError, TXID_PATTERN
from .ledger import InvoiceLedger
from .pricing import usd_per_trx
from .rpc import finalized_records

ASSETS = Path(__file__).with_name('static')
TOKEN = re.compile(r'^[A-Za-z0-9_-]{40,100}$')
CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
HEADERS = [('Cache-Control', 'private, no-store'), ('Referrer-Policy', 'no-referrer'),
           ('X-Content-Type-Options', 'nosniff'), ('X-Frame-Options', 'DENY'),
           ('Content-Security-Policy', CSP), ('Cross-Origin-Resource-Policy', 'same-origin')]


def strict_json(environ):
    try:
        size = int(environ.get('CONTENT_LENGTH', '0'))
    except ValueError as exc:
        raise CheckoutError('Invalid request size') from exc
    if not 0 < size <= 4096:
        raise CheckoutError('Request size outside bounds')
    if environ.get('CONTENT_TYPE', '').split(';')[0].lower() != 'application/json':
        raise CheckoutError('JSON body required')
    payload = environ['wsgi.input'].read(size)
    def unique_pairs(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise CheckoutError('Duplicate JSON field')
            result[k] = v
        return result
    try:
        data = json.loads(payload.decode('utf8'), object_pairs_hook=unique_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid numeric value')))
    except (ValueError, UnicodeError) as exc:
        raise CheckoutError('Invalid JSON') from exc
    if not isinstance(data, dict):
        raise CheckoutError('JSON object expected')
    return data


def escape(value):
    return html.escape(str(value), quote=True)


def qr_markup(address: str | None) -> str:
    if address is None:
        return '<div class="qr-placeholder">NO LIVE ADDRESS<br/>PREVIEW ONLY</div>'
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=5, border=1)
        qr.add_data(address)
        qr.make(fit=True)
        svg = qr.make_image(image_factory=SvgPathImage).to_string().decode('utf8')
        return svg[svg.find('<svg'):]
    except ImportError:
        return '<div class="qr-placeholder">COPY ADDRESS</div>'


def render_checkout(invoice: dict | None, *, token='', preview=False):
    if preview:
        data = {'product_title': 'Premium Digital Collection', 'usd': '4.00',
                'amount_sun': 0, 'address': None, 'status': 'preview',
                'expires_ms': 0}
    else:
        if invoice is None:
            raise CheckoutError('Invoice missing')
        data = invoice
    amount = f"{Decimal(data['amount_sun']) / Decimal(1_000_000):.6f}" if not preview else '—'
    expires = data['expires_ms']
    cfg = {'preview': preview, 'token': token if not preview else '',
           'address': data['address'], 'amount': amount, 'expires': expires,
           'status': data['status']}
    config = json.dumps(cfg, separators=(',', ':'), ensure_ascii=False).replace('<', '\\u003c')
    values = {
        'TRX_AMOUNT': escape(amount), 'USD_AMOUNT': escape(data['usd']),
        'ADDRESS': escape(data['address']) if data['address'] else 'No receiving address in preview',
        'PRODUCT_TITLE': escape(data['product_title']),
        'QR_MARKUP': qr_markup(data['address']),
        'INVOICE_JSON': config, 'TIME_TEXT': 'PREVIEW' if preview else '10:00',
        'COPY_DISABLED': 'disabled' if preview else '',
        'VERIFY_DISABLED': 'disabled' if preview or data['status'] == 'paid' else '',
        'INIT_MESSAGE': 'PREVIEW ONLY — DO NOT SEND FUNDS. No live invoice exists.' if preview else (
            'Payment confirmed on the TRON blockchain.' if data['status'] == 'paid' else
            'Waiting for the network to confirm a payment to this invoice address.'),
    }
    content = (ASSETS / 'checkout.html').read_text('utf8')
    for name, value in values.items():
        content = content.replace('{{' + name + '}}', value)
    if preview:
        content = content.replace('<body>', '<body class="demo"><div class="demo-ribbon">PREVIEW ONLY · NO REAL FUNDS · NOT CONNECTED TO THE LIVE STORE</div>', 1)
    return content.encode('utf8')


class TronGatewayApp:
    def __init__(self, db_filename: str, merchant_key: str, *, public_url='https://mojplaywin.com', api_key=''):
        url = urlsplit(public_url)
        if url.scheme != 'https' or url.netloc not in ('mojplaywin.com', 'www.mojplaywin.com') or url.path not in ('', '/'):
            raise CheckoutError('Only the owned HTTPS MojPlayWin origin is permitted')
        self.public_url = public_url.rstrip('/')
        self.ledger = InvoiceLedger(db_filename)
        self.api_key = api_key
        self.merchant_key = merchant_key
        if not isinstance(merchant_key, str) or len(merchant_key) < 32:
            raise CheckoutError('A strong merchant-only secret is required')
        self.ledger.initialize()

    def response(self, start, code, body, mime='application/json; charset=utf-8'):
        raw = body if isinstance(body, bytes) else body.encode('utf8')
        start(code, HEADERS + [('Content-Type', mime), ('Content-Length', str(len(raw)))])
        return [raw]

    def json_response(self, start, code, payload):
        return self.response(start, code, json.dumps(payload, separators=(',', ':'), ensure_ascii=False))

    def __call__(self, environ, start):
        path = environ.get('PATH_INFO', '')
        method = environ.get('REQUEST_METHOD', '')
        try:
            if method == 'GET' and path in ('/assets/checkout.css', '/assets/checkout.js'):
                kind = 'text/css' if path.endswith('.css') else 'text/javascript'
                return self.response(start, '200 OK', (ASSETS / path.rsplit('/', 1)[1]).read_bytes(), kind + '; charset=utf-8')
            # Reverse-proxy MUST set wsgi.url_scheme from trusted TLS state, never client-supplied XFP.
            if environ.get('wsgi.url_scheme') != 'https':
                return self.json_response(start, '403 Forbidden', {'error': 'HTTPS required'})
            if method == 'POST' and path == '/api/merchant/invoices':
                header = environ.get('HTTP_AUTHORIZATION', '')
                if not secrets.compare_digest(header.encode('utf8'), ('Bearer ' + self.merchant_key).encode('utf8')):
                    return self.json_response(start, '401 Unauthorized', {'error': 'Merchant authentication required'})
                obj = strict_json(environ)
                rate = usd_per_trx()  # NEVER accept customer-supplied conversion rates
                issued = self.ledger.issue(merchant_order_id=obj.get('order_id'),
                                           product_title=obj.get('product_title'),
                                           usd=obj.get('usd'), usd_per_trx=str(rate))
                return self.json_response(start, '201 Created', {
                    'order_id': issued.order_id, 'checkout_url': self.public_url + '/pay/' + issued.token + '/',
                    'amount_sun': issued.amount_sun, 'expires_ms': issued.expires_ms})
            match = re.fullmatch(r'/pay/([A-Za-z0-9_-]{40,100})/', path)
            if method == 'GET' and match:
                invoice = self.ledger.by_token(match.group(1))
                if not invoice:
                    return self.json_response(start, '404 Not Found', {'error': 'Invoice not found'})
                return self.response(start, '200 OK', render_checkout(invoice, token=match.group(1)), 'text/html; charset=utf-8')
            match = re.fullmatch(r'/api/status/([A-Za-z0-9_-]{40,100})', path)
            if method == 'GET' and match:
                invoice = self.ledger.by_token(match.group(1))
                if not invoice:
                    return self.json_response(start, '404 Not Found', {'error': 'Invoice not found'})
                public_status = 'paid' if invoice['status'] == 'paid' else (
                    'expired' if int(time.time() * 1000) > invoice['expires_ms'] else 'pending')
                return self.json_response(start, '200 OK', {'status': public_status,
                    'expires_ms': invoice['expires_ms'], 'order_id': invoice['merchant_order_id']})
            match = re.fullmatch(r'/api/verify/([A-Za-z0-9_-]{40,100})', path)
            if method == 'POST' and match:
                origin = environ.get('HTTP_ORIGIN')
                if origin != self.public_url:
                    return self.json_response(start, '403 Forbidden', {'error': 'Untrusted origin'})
                invoice = self.ledger.by_token(match.group(1))
                if not invoice:
                    return self.json_response(start, '404 Not Found', {'error': 'Invoice not found'})
                data = strict_json(environ)
                txid = data.get('txid')
                if not isinstance(txid, str) or not TXID_PATTERN.fullmatch(txid):
                    raise CheckoutError('Provide a valid 64-character transaction hash')
                tx, receipt = finalized_records(txid, api_key=self.api_key)
                saved = self.ledger.apply_proof(match.group(1), txid, tx, receipt)
                return self.json_response(start, '200 OK', {'status': saved['status'],
                    'message': 'On-chain payment finality established. Purchase delivery is managed by the store.'})
            return self.json_response(start, '404 Not Found', {'error': 'Not found'})
        except CheckoutError as exc:
            # Never auto-fulfill or report success if a proof, quote, or address is ambiguous.
            return self.json_response(start, '422 Unprocessable Entity', {'status': 'pending',
                'message': str(exc)})
        except (OSError, TimeoutError) as exc:
            return self.json_response(start, '503 Service Unavailable', {'status': 'pending',
                'message': 'Verification service temporarily unavailable. Do not pay twice.'})


def run_preview(port=8765):
    """Only a local design inspection; no invoices, wallets or RPC are enabled."""
    if not 1024 <= port <= 65535:
        raise SystemExit('Preview port outside bounds')
    def app(environ, start):
        path = environ.get('PATH_INFO')
        if path in ('/assets/checkout.css', '/assets/checkout.js'):
            fn = ASSETS / path.rsplit('/', 1)[1]
            raw = fn.read_bytes()
            start('200 OK', [('Content-Type', 'text/css' if str(fn).endswith('.css') else 'application/javascript'),
                            ('Cache-Control', 'no-store'), ('Content-Length', str(len(raw)))])
            return [raw]
        if path == '/':
            raw = render_checkout(None, preview=True)
            start('200 OK', [('Content-Type', 'text/html; charset=utf-8'), ('Cache-Control', 'no-store'),
                             ('Content-Security-Policy', CSP), ('Content-Length', str(len(raw)))])
            return [raw]
        start('404 Not Found', [('Content-Length', '0')])
        return [b'']
    with make_server('127.0.0.1', port, app) as server:
        print(f'MojPlayWin TRON read-only visual preview: http://127.0.0.1:{port}/', flush=True)
        server.serve_forever()