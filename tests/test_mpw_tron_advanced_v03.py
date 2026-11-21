"""Wallet-first native TRX acceptance contracts; all chain/network calls mocked."""
import io
import json
import os
import stat
import tempfile
import time
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from mpw_tron_pro.core import CheckoutError, ExpectedTransfer, inspect_finalized_trx
from mpw_tron_pro.ledger import InvoiceLedger
from mpw_tron_pro.reconcile import reconcile_pending
from mpw_tron_pro.webapp import TronGatewayApp, trust_wallet_payment_link, render_checkout
from mpw_tron_pro.worker import scan_once
from test_mpw_tron_pro import A1, A2, ISSUED, SUN, TX, records

KEY = 'Y'*48


class TestTrustWallet(unittest.TestCase):
    def test_signed_official_trust_wallet_payment_link_exact_amount(self):
        link = trust_wallet_payment_link(A1, SUN)
        parsed = urlsplit(link)
        self.assertEqual(parsed.scheme, 'https')
        self.assertEqual(parsed.netloc, 'link.trustwallet.com')
        self.assertEqual(parsed.path, '/send')
        self.assertEqual(parse_qs(parsed.query), {'asset':['c195'], 'address':[A1], 'amount':['12.500000']})

    def test_invalid_recipient_and_bool_amount_rejected(self):
        with self.assertRaises(CheckoutError): trust_wallet_payment_link('wrong', SUN)
        with self.assertRaises(CheckoutError): trust_wallet_payment_link(A1, True)
        with self.assertRaises(CheckoutError): trust_wallet_payment_link(A1, -1)

    def test_preview_has_no_payable_link(self):
        page = render_checkout(None, preview=True).decode()
        self.assertNotIn('https://link.trustwallet.com/send?', page)
        self.assertIn('id="trust-wallet-pay"', page)
        self.assertIn('aria-disabled="true"', page)
        self.assertIn('NO REAL FUNDS', page)
        self.assertIn('id="tronlink-pay"', page)
        self.assertIn('disabled', page)

    def test_live_buyer_has_real_prefilled_link_only_while_pending(self):
        base = {'product_title':'Digital Game','usd':'4.00','amount_sun':SUN,
                'address':A1,'expires_ms':ISSUED + 600000,'status':'pending'}
        with patch('mpw_tron_pro.webapp.time.time',return_value=ISSUED/1000 + 30):
            page = render_checkout(base, token='L'*48).decode()
        self.assertIn('link.trustwallet.com/send?asset=c195', page)
        self.assertIn('amount=12.500000', page)
        with patch('mpw_tron_pro.webapp.time.time',return_value=ISSUED/1000 + 601):
            expired = render_checkout(base, token='L'*48).decode()
        self.assertNotIn('link.trustwallet.com/send?', expired)
        self.assertIn('aria-disabled="true"', expired)

    def test_paid_invoice_does_not_have_a_pay_link(self):
        base = {'product_title':'Game','usd':'4.00','amount_sun':SUN,
                'address':A1,'expires_ms':ISSUED + 600000,'status':'paid'}
        with patch('mpw_tron_pro.webapp.time.time',return_value=ISSUED/1000 + 5):
            page = render_checkout(base, token='L'*48).decode()
        self.assertNotIn('link.trustwallet.com/send?', page)

    def test_js_wallet_only_signs_after_explicit_tron_mainnet_guard(self):
        js = (Path(__file__).resolve().parents[1]/'mpw_tron_pro/static/checkout.js').read_text()
        for text in ('eth_requestAccounts','eth_chainId','0x2b6653dc','sendTrx','trx.sign',
                     'sendRawTransaction','amountSun','send twice','changeStatus(\'checking\')'):
            self.assertIn(text,js)
        self.assertNotIn('privateKey', js)
        self.assertNotIn('mnemonic', js)


class AdvancedDbCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'gateway.sqlite3'
        self.ledger = InvoiceLedger(self.db)
        self.ledger.initialize()
        self.ledger.add_public_address(A1)
        self.ledger.add_public_address(A2)
        self.inv = self.ledger.issue(merchant_order_id='MPW-ORDER-00001',product_title='Game',
            usd='4.00',usd_per_trx='0.32',now_ms=ISSUED)

    def tearDown(self): self.tmp.cleanup()


class TestAmountReview(AdvancedDbCase):
    def test_record_finalized_underpay_without_credit(self):
        body,receipt=records(amount=SUN-1)
        review=self.ledger.record_mismatched_payment(1,TX,body,receipt)
        self.assertEqual(review['status'],'underpaid')
        self.assertTrue(review['new'])
        self.assertEqual(self.ledger.by_token(self.inv.token)['status'],'pending')
        self.assertEqual(self.ledger.public_state(self.ledger.by_token(self.inv.token))['status'],'underpaid')
        self.assertFalse(self.ledger.public_state(self.ledger.by_token(self.inv.token))['payment_confirmed'])

    def test_record_finalized_overpay_requires_review(self):
        body,receipt=records(amount=SUN+1)
        self.assertEqual(self.ledger.record_mismatched_payment(1,TX,body,receipt)['status'],'overpaid')
        self.assertEqual(self.ledger.by_token(self.inv.token)['status'],'pending')

    def test_observation_idempotent_not_double_counted(self):
        body,receipt=records(amount=SUN-1)
        a=self.ledger.record_mismatched_payment(1,TX,body,receipt)
        b=self.ledger.record_mismatched_payment(1,TX,body,receipt)
        self.assertTrue(a['new'])
        self.assertFalse(b['new'])
        with self.ledger._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM payment_observations').fetchone()[0],1)

    def test_reject_other_recipient_even_for_partial(self):
        body,receipt=records(dest=A2,amount=SUN-1)
        with self.assertRaises(CheckoutError): self.ledger.record_mismatched_payment(1,TX,body,receipt)
        self.assertEqual(self.ledger.public_state(self.ledger.by_token(self.inv.token))['status'],'pending' if ISSUED + 5000 > int(time.time()*1000) else 'expired')

    def test_reject_payment_mismatched_txid_and_failed_receipt(self):
        body,receipt=records(amount=SUN-1)
        receipt['id']='b'*64
        with self.assertRaises(CheckoutError): self.ledger.record_mismatched_payment(1,TX,body,receipt)
        body,receipt=records(amount=SUN-1,result='FAILED')
        with self.assertRaises(CheckoutError): self.ledger.record_mismatched_payment(1,TX,body,receipt)

    def test_early_transaction_not_valid_payment(self):
        body,receipt=records(block_ms=ISSUED-20000)
        with self.assertRaises(CheckoutError):
            inspect_finalized_trx(body,receipt,ExpectedTransfer(TX,A1,SUN,ISSUED,ISSUED+600000))

    def test_auto_scanner_classifies_underpay_but_does_not_settle(self):
        body,receipt=records(amount=SUN-10)
        res=reconcile_pending(self.ledger,discover=lambda *a,**k:[TX],fetch=lambda *a,**k:(body,receipt))
        self.assertEqual(res['settled'],0)
        self.assertEqual(res['underpaid'],1)
        again=reconcile_pending(self.ledger,discover=lambda *a,**k:[TX],fetch=lambda *a,**k:(body,receipt))
        self.assertEqual(again['underpaid'],0)


class TestMerchantAndMonitoring(AdvancedDbCase):
    def request(self, app, path, *, method='GET', payload=None, merchant_key=None, origin=None):
        body=json.dumps(payload).encode() if payload is not None else b''
        env={'PATH_INFO':path,'REQUEST_METHOD':method,'wsgi.url_scheme':'https',
             'wsgi.input':io.BytesIO(body),'CONTENT_LENGTH':str(len(body)),
             'CONTENT_TYPE':'application/json'}
        if merchant_key is not None: env['HTTP_AUTHORIZATION']='Bearer '+merchant_key
        if origin is not None: env['HTTP_ORIGIN']=origin
        state={}
        def start(code,headers): state.update(code=code,headers=dict(headers))
        data=b''.join(app(env,start))
        return state,json.loads(data)

    def test_merchant_status_endpoint_only_for_owner(self):
        app=TronGatewayApp(str(self.db),KEY)
        url='/api/merchant/orders/MPW-ORDER-00001'
        anon,_=self.request(app,url)
        self.assertTrue(anon['code'].startswith('401'))
        ok,state=self.request(app,url,merchant_key=KEY)
        self.assertEqual(state['order_id'],'MPW-ORDER-00001')
        self.assertFalse(state['payment_confirmed'])
        self.assertIsNone(state['txid'])
        self.assertNotIn('address',state)
        self.assertEqual(state['fulfillment'],'not_integrated')
        self.ledger.apply_proof(self.inv.token,TX,*records())
        ok,state=self.request(app,url,merchant_key=KEY)
        self.assertTrue(state['payment_confirmed'])
        self.assertEqual(state['txid'],TX)

    def test_public_status_reflects_scanner_health_and_review(self):
        app=TronGatewayApp(str(self.db),KEY)
        state,data=self.request(app,'/api/status/'+self.inv.token)
        self.assertEqual(data['monitoring'],'not_configured')
        self.assertFalse(data['payment_confirmed'])
        self.ledger.record_mismatched_payment(1,TX,*records(amount=SUN+1))
        state,data=self.request(app,'/api/status/'+self.inv.token)
        self.assertEqual(data['status'],'overpaid')
        self.assertFalse(data['payment_confirmed'])

    def test_rate_limiter_bounded_without_network_calls(self):
        for i in range(4):
            self.assertTrue(self.ledger.allow_verification(1, now_ms=ISSUED+i*1000))
        self.assertFalse(self.ledger.allow_verification(1,now_ms=ISSUED+5000))
        self.assertTrue(self.ledger.allow_verification(1,now_ms=ISSUED+61000))

    def test_api_verify_429_and_no_rpc_call(self):
        app=TronGatewayApp(str(self.db),KEY)
        for i in range(4):self.ledger.allow_verification(1,now_ms=ISSUED+i*1000)
        with patch('mpw_tron_pro.ledger.time.time',return_value=ISSUED/1000+5):
            with patch('mpw_tron_pro.webapp.finalized_records',side_effect=AssertionError('Called RPC')):
                response,data=self.request(app,'/api/verify/'+self.inv.token,
                    method='POST',payload={'txid':TX},origin='https://mojplaywin.com')
        self.assertTrue(response['code'].startswith('429'))
        self.assertEqual(response['headers']['Retry-After'],'30')

    def test_api_underpay_is_202_not_paid(self):
        app=TronGatewayApp(str(self.db),KEY)
        with patch('mpw_tron_pro.webapp.finalized_records',return_value=records(amount=SUN-5)):
            response,data=self.request(app,'/api/verify/'+self.inv.token,
                method='POST',payload={'txid':TX},origin='https://mojplaywin.com')
        self.assertTrue(response['code'].startswith('202'))
        self.assertEqual(data['status'],'underpaid')
        self.assertEqual(self.ledger.by_token(self.inv.token)['status'],'pending')

    def test_worker_requires_private_directory(self):
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(CheckoutError):
                scan_once(str(self.db),str(Path(other)/'worker.lock'),
                          reconcile=lambda ledger,**kw:{'scanned':0,'settled':0,'failed_scans':0,'requires_review':0})

    def test_worker_records_true_heartbeat_and_no_financial_claim(self):
        # TemporaryDirectory is private on POSIX; no actual chain queried.
        self.assertFalse(os.stat(self.db.parent).st_mode & 0o077)
        outcome=scan_once(str(self.db),str(self.db.parent/'worker.lock'),
            reconcile=lambda ledger,**kw:{'scanned':0,'settled':0,'failed_scans':0,'requires_review':0})
        self.assertEqual(outcome['scanned'],0)
        self.assertEqual(self.ledger.monitoring(),'running')
        self.assertEqual(self.ledger.public_state(self.ledger.by_token(self.inv.token))['status'],'expired')
        self.assertEqual(self.ledger.by_token(self.inv.token)['status'],'pending')

    def test_failed_scan_does_not_report_healthy(self):
        self.ledger.record_scan_run({'scanned':1,'settled':0,'failed_scans':1,'requires_review':0})
        self.assertEqual(self.ledger.monitoring(),'degraded')
        self.ledger.record_scan_run({'scanned':1,'settled':0,'failed_scans':0,'requires_review':0},now_ms=ISSUED)
        self.assertEqual(self.ledger.monitoring(),'stale')


if __name__=='__main__':unittest.main()

class TestAlreadyPaidNoNetwork(AdvancedDbCase):
    def test_redundant_paid_payment_checks_never_query_mainnet(self):
        self.ledger.apply_proof(self.inv.token,TX,*records())
        app=TronGatewayApp(str(self.db),KEY)
        def request(txid):
            payload=json.dumps({'txid':txid}).encode()
            env={'PATH_INFO':'/api/verify/'+self.inv.token,'REQUEST_METHOD':'POST',
                 'wsgi.url_scheme':'https','HTTP_ORIGIN':'https://mojplaywin.com',
                 'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(payload)),
                 'wsgi.input':io.BytesIO(payload)}
            state={}
            def start(status,headers): state['status']=status
            raw=b''.join(app(env,start))
            return state['status'],json.loads(raw)
        with patch('mpw_tron_pro.webapp.finalized_records',side_effect=AssertionError('No RPC on already paid')):
            status,proof=request(TX)
            self.assertTrue(status.startswith('200'))
            self.assertEqual(proof['status'],'paid')
            status,proof=request('b'*64)
            self.assertTrue(status.startswith('409'))