import hashlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from mpw_tron_pro.core import CheckoutError, ExpectedTransfer, sun_quote, tron_address_hex, verify_finalized_trx
from mpw_tron_pro.ledger import InvoiceLedger
from mpw_tron_pro.webapp import TronGatewayApp, render_checkout, strict_json, qr_markup
from mpw_tron_pro.rpc import finalized_records

ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


def address(seed):
    data = bytes.fromhex('41' + f'{seed:040x}')
    check = hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
    val = int.from_bytes(data + check, 'big')
    out = ''
    while val:
        val, d = divmod(val, 58)
        out = ALPHABET[d] + out
    return out

A1 = address(101)
A2 = address(202)
TX = 'a' * 64
ISSUED = 1760000000000
SUN = 12500000


def records(dest=A1, amount=SUN, txid=TX, block_ms=ISSUED + 90000, result='SUCCESS', contract='TransferContract'):
    body = {'txID': txid, 'ret': [{'contractRet': result}], 'raw_data': {'contract': [
        {'type': contract, 'parameter': {'type_url': 'type.googleapis.com/protocol.TransferContract',
          'value': {'to_address': tron_address_hex(dest), 'owner_address': tron_address_hex(A2),
                    'amount': amount}}}]}}
    receipt = {'id': txid, 'blockNumber': 701, 'blockTimeStamp': block_ms,
               'receipt': {'result': 'SUCCESS'}}
    return body, receipt


class TestTRONCore(unittest.TestCase):
    def test_checksum_and_prefix(self):
        self.assertEqual(len(A1), 34)
        self.assertEqual(tron_address_hex(A1), '41' + f'{101:040x}'.upper())

    def test_checksum_corrupted_fails(self):
        with self.assertRaises(CheckoutError): tron_address_hex(A1[:-1] + ('1' if A1[-1] != '1' else '2'))

    def test_invalid_address(self):
        for bad in ['', '0' * 34, 'TRON', 'T' + '0' * 33]:
            with self.subTest(bad=bad), self.assertRaises(CheckoutError): tron_address_hex(bad)

    def test_quote_round_up_precisely(self):
        self.assertEqual(sun_quote('4.00', '0.32'), 12_500_000)
        self.assertEqual(sun_quote('0.01', '0.30'), 33_334)

    def test_nonfinite_invalid_quote_and_bool(self):
        for usd, rate in [('NaN', '1'), ('Infinity', '1'), ('0', '1'), ('4.0001', '.25'), ('4', '0'), ('1', '1000')]:
            with self.subTest(usd=usd, rate=rate), self.assertRaises(CheckoutError): sun_quote(usd, rate)

    def test_finalized_exact_native_trx(self):
        tx, receipt = records()
        proof = verify_finalized_trx(tx, receipt, ExpectedTransfer(TX, A1, SUN, ISSUED, ISSUED + 600000))
        self.assertEqual(proof.block_number, 701)
        self.assertEqual(proof.amount_sun, SUN)

    def test_reject_wrong_destination(self):
        tx, receipt = records(dest=A2)
        with self.assertRaisesRegex(CheckoutError, 'recipient'):
            verify_finalized_trx(tx, receipt, ExpectedTransfer(TX, A1, SUN, ISSUED, ISSUED + 600000))

    def test_reject_underpay_and_overpay(self):
        for amt in (SUN - 1, SUN + 1):
            tx, receipt = records(amount=amt)
            with self.subTest(amt=amt), self.assertRaises(CheckoutError):
                verify_finalized_trx(tx, receipt, ExpectedTransfer(TX, A1, SUN, ISSUED, ISSUED + 600000))

    def test_reject_unfinalized_missing_receipt(self):
        tx, _ = records()
        with self.assertRaises(CheckoutError):
            verify_finalized_trx(tx, {}, ExpectedTransfer(TX, A1, SUN, ISSUED, ISSUED + 600000))

    def test_reject_wrong_contract(self):
        tx, receipt = records(contract='TriggerSmartContract')
        with self.assertRaises(CheckoutError):
            verify_finalized_trx(tx, receipt, ExpectedTransfer(TX, A1, SUN, ISSUED, ISSUED + 600000))

    def test_reject_failed_execution(self):
        tx, receipt = records(result='FAILED')
        with self.assertRaises(CheckoutError):
            verify_finalized_trx(tx, receipt, ExpectedTransfer(TX, A1, SUN, ISSUED, ISSUED + 600000))

    def test_reject_wrong_txid(self):
        tx, receipt = records(txid='b' * 64)
        with self.assertRaises(CheckoutError):
            verify_finalized_trx(tx, receipt, ExpectedTransfer(TX, A1, SUN, ISSUED, ISSUED + 600000))

    def test_reject_expired_block(self):
        tx, receipt = records(block_ms=ISSUED + 600000 + 180001)
        with self.assertRaises(CheckoutError):
            verify_finalized_trx(tx, receipt, ExpectedTransfer(TX, A1, SUN, ISSUED, ISSUED + 600000))

    def test_reject_malformed_transaction_body(self):
        tx, receipt = records()
        tx['raw_data']['contract'].append(tx['raw_data']['contract'][0])
        with self.assertRaises(CheckoutError):
            verify_finalized_trx(tx, receipt, ExpectedTransfer(TX, A1, SUN, ISSUED, ISSUED + 600000))


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ledger = InvoiceLedger(Path(self.dir.name) / 'ledger.sqlite3')
        self.ledger.initialize()
        self.ledger.add_public_address(A1)
        self.ledger.add_public_address(A2)

    def tearDown(self):
        self.dir.cleanup()

    def issue(self, order='MPW-ORDER-00001'):
        return self.ledger.issue(merchant_order_id=order, product_title='Premium Game',
                                 usd='4.00', usd_per_trx='0.32', now_ms=ISSUED)

    def test_unique_address_allocation(self):
        first = self.issue()
        second = self.issue('MPW-ORDER-00002')
        self.assertNotEqual(first.address, second.address)
        self.assertEqual(first.amount_sun, SUN)

    def test_fails_closed_without_unused_address(self):
        self.issue()
        self.issue('MPW-ORDER-00002')
        with self.assertRaisesRegex(CheckoutError, 'No unique'):
            self.issue('MPW-ORDER-00003')

    def test_duplicate_order_must_not_reserve_another_address(self):
        self.issue()
        with self.assertRaises(CheckoutError): self.issue()
        self.assertEqual(self.issue('MPW-ORDER-00002').address, A2)

    def test_capability_is_unforgeable(self):
        first = self.issue()
        self.assertEqual(self.ledger.by_token(first.token)['merchant_order_id'], first.order_id)
        self.assertIsNone(self.ledger.by_token(first.token[:-1] + '_'))
        with self.ledger._connect() as db:
            self.assertNotIn(first.token, str(db.execute('SELECT * FROM invoices').fetchall()))

    def test_marks_paid_once_only_after_finality(self):
        inv = self.issue()
        body, receipt = records()
        saved = self.ledger.apply_proof(inv.token, TX, body, receipt)
        self.assertEqual(saved['status'], 'paid')
        self.assertEqual(self.ledger.apply_proof(inv.token, TX, body, receipt)['status'], 'paid')
        with self.assertRaises(CheckoutError): self.ledger.apply_proof(inv.token, 'b'*64, body, receipt)

    def test_payment_destination_cannot_be_reused_for_other_order(self):
        inv1 = self.issue()
        inv2 = self.issue('MPW-ORDER-00002')
        body, receipt = records(dest=inv1.address)
        self.ledger.apply_proof(inv1.token, TX, body, receipt)
        with self.assertRaises(CheckoutError): self.ledger.apply_proof(inv2.token, TX, body, receipt)
        self.assertEqual(self.ledger.by_token(inv2.token)['status'], 'pending')

    def test_failed_validation_never_marks_paid(self):
        inv = self.issue()
        body, receipt = records(amount=SUN - 5)
        with self.assertRaises(CheckoutError): self.ledger.apply_proof(inv.token, TX, body, receipt)
        self.assertEqual(self.ledger.by_token(inv.token)['status'], 'pending')

    def test_unique_txid_constraint_even_with_external_mistake(self):
        self.issue(); self.issue('MPW-ORDER-00002')
        with self.ledger._connect() as db:
            db.execute("UPDATE invoices SET status='paid',txid=? WHERE merchant_order_id=?", (TX, 'MPW-ORDER-00001'))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE invoices SET status='paid',txid=? WHERE merchant_order_id=?", (TX, 'MPW-ORDER-00002'))


class TestWebSecurity(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.app = TronGatewayApp(str(Path(self.dir.name) / 'db.sqlite3'), 'M'*48)
        self.app.ledger.add_public_address(A1)

    def tearDown(self): self.dir.cleanup()

    def request(self, path, *, method='GET', body=None, headers=None, https=True):
        data = json.dumps(body).encode() if body is not None else b''
        env = {'PATH_INFO': path, 'REQUEST_METHOD': method,
               'wsgi.url_scheme': 'https' if https else 'http',
               'wsgi.input': io.BytesIO(data), 'CONTENT_LENGTH': str(len(data)),
               'CONTENT_TYPE': 'application/json'}
        if headers: env.update(headers)
        captured = {}
        def start(status, resp_headers): captured['status'], captured['headers'] = status, dict(resp_headers)
        result = b''.join(self.app(env, start))
        return captured, result

    def test_fails_non_tls_and_header_protection(self):
        result, data = self.request('/api/merchant/invoices', https=False, method='POST')
        self.assertTrue(result['status'].startswith('403'))
        self.assertEqual(result['headers']['Referrer-Policy'], 'no-referrer')
        self.assertIn("frame-ancestors 'none'", result['headers']['Content-Security-Policy'])

    def test_merchant_must_authenticate(self):
        result, data = self.request('/api/merchant/invoices', method='POST', body={'usd':'4.00'})
        self.assertTrue(result['status'].startswith('401'))

    def test_reject_browser_price_injection_or_missing_stock(self):
        payload = {'order_id':'MPW-ORDER-00001', 'product_title':'Game', 'usd':'4.00'}
        with patch('mpw_tron_pro.webapp.usd_per_trx', return_value=Decimal('.32')):
            ok, data = self.request('/api/merchant/invoices', method='POST', body=payload,
                                    headers={'HTTP_AUTHORIZATION': 'Bearer ' + 'M'*48})
        self.assertTrue(ok['status'].startswith('201'), data)
        u = json.loads(data)['checkout_url']; self.assertIn('/pay/', u)
        self.assertNotIn('address', json.loads(data))
        token = u.rsplit('/', 2)[1]
        info, view = self.request('/pay/' + token + '/')
        self.assertTrue(info['status'].startswith('200'))
        self.assertIn(A1.encode(), view)
        self.assertNotIn(b'PRIVATE_KEY', view)
        status, state = self.request('/api/status/' + token)
        self.assertEqual(json.loads(state)['status'], 'pending')
        attempt, _ = self.request('/api/verify/' + token, method='POST', body={'txid': TX})
        self.assertTrue(attempt['status'].startswith('403'))

    def test_quote_preview_never_shows_live_address(self):
        view = render_checkout(None, preview=True)
        self.assertIn(b'PREVIEW ONLY', view)
        self.assertNotIn(A1.encode(), view)
        self.assertIn(b'disabled', view)

    def test_duplicate_json_keys_rejected(self):
        env = {'CONTENT_LENGTH':str(len(b'{"usd":"4","usd":"0"}')),
               'CONTENT_TYPE':'application/json',
               'wsgi.input':io.BytesIO(b'{"usd":"4","usd":"0"}')}
        with self.assertRaises(CheckoutError): strict_json(env)


if __name__ == '__main__': unittest.main()

class TestAutoDiscovery(unittest.TestCase):
    class Response:
        status = 200
        def __init__(self, obj): self.buffer = io.BytesIO(json.dumps(obj).encode('utf8'))
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, size): return self.buffer.read(size)

    def test_incoming_candidate_requires_confirmed_index(self):
        from mpw_tron_pro.reconcile import incoming_candidates
        seen_urls = []
        def fake(req, timeout):
            seen_urls.append(req.full_url)
            return self.Response({'success': True, 'data': [{'txID': TX}], 'meta': {}})
        self.assertEqual(incoming_candidates(A1, ISSUED, ISSUED + 600000, opener=fake), [TX])
        self.assertIn('only_confirmed=true', seen_urls[0]); self.assertIn('only_to=true', seen_urls[0])

    def test_incoming_candidate_pagination(self):
        from mpw_tron_pro.reconcile import incoming_candidates
        replies = iter([
            {'success': True, 'data': [{'txID': TX}], 'meta': {'fingerprint':'abc01'}},
            {'success': True, 'data': [{'txID': 'b'*64}], 'meta': {}},
        ])
        self.assertEqual(incoming_candidates(A1, ISSUED, ISSUED + 600000,
                         opener=lambda req, timeout: self.Response(next(replies))), [TX, 'b'*64])

    def test_incoming_candidate_fails_closed_on_malformed_index(self):
        from mpw_tron_pro.reconcile import incoming_candidates
        with self.assertRaises(CheckoutError): incoming_candidates(A1, ISSUED, ISSUED + 600000,
            opener=lambda req,timeout: self.Response({'success':False,'data':[],'meta':{}}))

    def test_incoming_candidate_fails_closed_if_too_many_pages(self):
        from mpw_tron_pro.reconcile import incoming_candidates
        counter = iter(range(100))
        def fake(req,timeout):
            return self.Response({'success':True, 'data':[{'txID':TX}],
                                  'meta': {'fingerprint':f'page{next(counter)}'}})
        with self.assertRaises(CheckoutError):
            incoming_candidates(A1, ISSUED, ISSUED + 600000, opener=fake,max_pages=2)

    def test_auto_reconcile_requires_real_finalized_proof(self):
        from mpw_tron_pro.reconcile import reconcile_pending
        with tempfile.TemporaryDirectory() as folder:
            ledger=InvoiceLedger(Path(folder)/'db.sqlite')
            ledger.initialize();ledger.add_public_address(A1)
            inv=ledger.issue(merchant_order_id='MPW-ORDER-00001',product_title='Game',
                             usd='4.00',usd_per_trx='.32',now_ms=ISSUED)
            scan=lambda address,issued,expires,api_key: [TX]
            fetch=lambda txid,api_key: records()
            outcome=reconcile_pending(ledger,discover=scan,fetch=fetch)
            self.assertEqual(outcome['settled'],1)
            self.assertEqual(ledger.by_token(inv.token)['status'],'paid')

    def test_auto_reconcile_does_not_settle_invalid_payment(self):
        from mpw_tron_pro.reconcile import reconcile_pending
        with tempfile.TemporaryDirectory() as folder:
            ledger=InvoiceLedger(Path(folder)/'db.sqlite')
            ledger.initialize();ledger.add_public_address(A1)
            inv=ledger.issue(merchant_order_id='MPW-ORDER-00001',product_title='Game',
                             usd='4.00',usd_per_trx='.32',now_ms=ISSUED)
            outcome=reconcile_pending(ledger,discover=lambda *args,**kwargs:[TX],
                    fetch=lambda *args,**kwargs:records(amount=SUN-1))
            self.assertEqual(outcome['settled'],0)
            self.assertEqual(outcome['underpaid'],1)
            self.assertEqual(ledger.by_token(inv.token)['status'],'pending')
            self.assertEqual(ledger.public_state(ledger.by_token(inv.token))['status'],'underpaid')