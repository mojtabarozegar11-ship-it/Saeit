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
from urllib.parse import urlsplit, urlencode
from wsgiref.simple_server import make_server

from .core import CheckoutError, TXID_PATTERN, tron_address_hex
from .ledger import InvoiceLedger, ORDER_ID
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


def trust_wallet_payment_link(address: str, amount_sun: int) -> str:
    """Official Trust Wallet payment deeplink. Never embed private keys or payment claims."""
    tron_address_hex(address)
    if type(amount_sun) is not int or not 0 < amount_sun <= 10**13:
        raise CheckoutError('Invalid TRX amount')
    amount = format(Decimal(amount_sun) / Decimal(1_000_000), '.6f')
    return 'https://link.trustwallet.com/send?' + urlencode({
        'asset': 'c195', 'address': address, 'amount': amount})


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
    wallet_ready = (not preview and bool(data['address']) and data['status'] == 'pending'
                    and int(time.time()*1000) <= expires)
    wallet_link = trust_wallet_payment_link(data['address'], data['amount_sun']) if wallet_ready else '#'
    cfg = {'preview': preview, 'token': token if not preview else '',
           'address': data['address'], 'amount': amount, 'expires': expires,
           'status': data['status'], 'amountSun': data['amount_sun'],
           'serverNow': int(time.time()*1000), 'monitoring': data.get('monitoring','not_configured'),
           'fulfillment':data.get('fulfillment','not_paid')}
    config = json.dumps(cfg, separators=(',', ':'), ensure_ascii=False).replace('<', '\\u003c')
    values = {
        'TRX_AMOUNT': escape(amount), 'USD_AMOUNT': escape(data['usd']),
        'ADDRESS': escape(data['address']) if data['address'] else 'No receiving address in preview',
        'PRODUCT_TITLE': escape(data['product_title']),
        'QR_MARKUP': qr_markup(data['address']),
        'INVOICE_JSON': config, 'TIME_TEXT': 'PREVIEW' if preview else '10:00',
        'COPY_DISABLED': 'disabled' if not wallet_ready else '',
        'VERIFY_DISABLED': 'disabled' if preview or data['status'] == 'paid' else '',
        'TRUST_URL': escape(wallet_link),
        'TRUST_DISABLED': 'aria-disabled="true" tabindex="-1"' if not wallet_ready else '',
        'WALLET_DISABLED': 'disabled' if not wallet_ready else '',
        'INIT_MESSAGE': 'PREVIEW ONLY — DO NOT SEND FUNDS. No live invoice exists.' if preview else (
            'On-chain payment confirmed. Digital delivery is being processed automatically when store integration is active.' if data['status'] == 'paid' else
            'Amount mismatch found in a finalized transfer. Contact support; do not pay again.'
            if data['status'] in ('underpaid','overpaid') else
            'Invoice expired. Do not begin a new transfer.' if data['status']=='expired' else
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

    def response(self, start, code, body, mime='application/json; charset=utf-8', extra_headers=()):
        raw = body if isinstance(body, bytes) else body.encode('utf8')
        start(code, HEADERS + list(extra_headers) + [('Content-Type', mime), ('Content-Length', str(len(raw)))])
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
            # Store-side, merchant-only read endpoint for durable fulfillment integration.
            merchant_match = re.fullmatch(r'/api/merchant/orders/([A-Za-z0-9_-]{10,80})', path)
            if method == 'GET' and merchant_match:
                header = environ.get('HTTP_AUTHORIZATION', '')
                if not secrets.compare_digest(header.encode('utf8'), ('Bearer ' + self.merchant_key).encode('utf8')):
                    return self.json_response(start, '401 Unauthorized', {'error': 'Merchant authentication required'})
                order = self.ledger.by_order(merchant_match.group(1))
                if order is None:
                    return self.json_response(start, '404 Not Found', {'error': 'Order not found'})
                public = self.ledger.public_state(order)
                return self.json_response(start, '200 OK', {**public, 'txid': order['txid'] if public['payment_confirmed'] else None,
                    'block_number': order['block_number'] if public['payment_confirmed'] else None,
                    'paid_ms': order['paid_ms'] if public['payment_confirmed'] else None,
                    'amount_sun': order['amount_sun'], 'usd': order['usd']})
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
                buyer_state = self.ledger.public_state(invoice)
                return self.response(start, '200 OK', render_checkout({**invoice, 'status':buyer_state['status'],
                    'monitoring':buyer_state['monitoring'],
                    'fulfillment':buyer_state['fulfillment']},
                    token=match.group(1)), 'text/html; charset=utf-8')
            match = re.fullmatch(r'/api/status/([A-Za-z0-9_-]{40,100})', path)
            if method == 'GET' and match:
                invoice = self.ledger.by_token(match.group(1))
                if not invoice:
                    return self.json_response(start, '404 Not Found', {'error': 'Invoice not found'})
                state = self.ledger.public_state(invoice)
                if state['payment_confirmed']:
                    state['txid'] = invoice['txid']
                return self.json_response(start, '200 OK', state)
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
                if invoice['status'] == 'paid':
                    if secrets.compare_digest(invoice['txid'] or '', txid):
                        return self.json_response(start, '200 OK', {'status':'paid','txid':txid,
                            'message':'Payment verified. Waiting for confirmed store delivery.'})
                    return self.json_response(start, '409 Conflict', {'status':'paid',
                        'message':'This invoice was already paid with a different transaction.'})
                if not self.ledger.allow_verification(invoice['id']):
                    return self.response(start, '429 Too Many Requests', json.dumps({
                        'status':'pending', 'message':'Too many verification requests. Automatic scanning continues.'}),
                        extra_headers=[('Retry-After', '30')])
                tx, receipt = finalized_records(txid, api_key=self.api_key)
                try:
                    saved = self.ledger.apply_proof(match.group(1), txid, tx, receipt)
                except CheckoutError:
                    # Only a finalized, correct-recipient transfer can enter manual review;
                    # all other failures retain pending status and are never credited.
                    try:
                        review = self.ledger.record_mismatched_payment(invoice['id'], txid, tx, receipt)
                    except CheckoutError:
                        raise
                    return self.json_response(start, '202 Accepted', {'status': review['status'],
                        'message': 'Transfer received, but amount differs. Do not pay again; contact merchant support.'})
                return self.json_response(start, '200 OK', {'status': saved['status'],
                    'txid': txid, 'message': 'On-chain payment confirmed. Automatic delivery is queued pending store acknowledgement.'})
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