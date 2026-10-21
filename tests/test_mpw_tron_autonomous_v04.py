"""Automated payment to idempotent fulfillment contracts; all external calls simulated."""
import hashlib
import hmac
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mpw_tron_pro.core import CheckoutError
from mpw_tron_pro.ledger import InvoiceLedger
from mpw_tron_pro.store_delivery import (DeliveryUnavailable, validate_endpoint,
    payload_for, delivery_request, send_to_store, drain_outbox)
from mpw_tron_pro.reconcile import reconcile_pending
from mpw_tron_pro.worker import scan_once
from mpw_tron_pro.store_receiver_contract import verify_store_event
from test_mpw_tron_pro import A1,A2,ISSUED,SUN,TX,records,address

DEST='https://mojplaywin.com/api/payments/tron/fulfill/'
SECRET='R'*48

class DbTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Path(self.temp.name)/'checkout.sqlite3'
        self.ledger=InvoiceLedger(self.db)
        self.ledger.initialize()
        self.ledger.add_public_address(A1)
        self.inv=self.ledger.issue(merchant_order_id='MPW-ORDER-AUTOTEST-1',
                   product_title='Digital Game',usd='4.00',usd_per_trx='0.32',now_ms=ISSUED)

    def tearDown(self):self.temp.cleanup()

    def settle(self):
        body,receipt=records()
        return self.ledger.apply_proof(self.inv.token,TX,body,receipt)

class TestAtomicDelivery(DbTest):
    def test_event_created_atomically_with_verified_payment(self):
        self.assertFalse(self.ledger.delivery_backlog())
        self.settle()
        self.assertEqual(self.ledger.delivery_backlog(),{'queued':1})
        self.assertEqual(self.ledger.public_state(self.ledger.by_token(self.inv.token))['fulfillment'],'pending_delivery')

    def test_invalid_proof_no_event_no_fulfillment(self):
        body,receipt=records(amount=SUN-1)
        with self.assertRaises(CheckoutError):self.ledger.apply_proof(self.inv.token,TX,body,receipt)
        self.assertEqual(self.ledger.delivery_backlog(),{})

    def test_repeated_identical_settlement_one_event(self):
        self.settle();self.settle()
        with self.ledger._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM delivery_outbox').fetchone()[0],1)

    def test_background_finalization_also_generates_event(self):
        body,receipt=records()
        self.ledger.settle_discovered(1,TX,body,receipt)
        self.assertEqual(self.ledger.delivery_backlog(),{'queued':1})

    def test_claim_is_exclusive_even_across_ledger_process_instances(self):
        self.settle()
        a=self.ledger.claim_delivery(now_ms=ISSUED+200000)
        b=InvoiceLedger(self.db).claim_delivery(now_ms=ISSUED+200000)
        self.assertIsNone(b)
        self.assertTrue(a['lease_token'])
        self.assertIn(TX,a['txid'])

    def test_crashed_lease_retried_after_expiration_same_event(self):
        self.settle()
        a=self.ledger.claim_delivery(now_ms=ISSUED+100000)
        self.assertIsNone(self.ledger.claim_delivery(now_ms=ISSUED+100001))
        b=self.ledger.claim_delivery(now_ms=ISSUED+220001)
        self.assertEqual(b['event_id'],a['event_id'])
        self.assertNotEqual(b['lease_token'],a['lease_token'])
        with self.assertRaisesRegex(CheckoutError,'lease'):
            self.ledger.finish_delivery(1,a['lease_token'],receipt_id='receipt-12345')

    def test_success_ack_marks_delivered(self):
        self.settle(); claimed=self.ledger.claim_delivery()
        self.ledger.finish_delivery(1,claimed['lease_token'],receipt_id='delivery-123456')
        state=self.ledger.public_state(self.ledger.by_token(self.inv.token))
        self.assertEqual(state['fulfillment'],'delivered')
        self.assertIsNone(self.ledger.claim_delivery())

    def test_bad_receipt_does_not_mark_delivered(self):
        self.settle();claimed=self.ledger.claim_delivery()
        with self.assertRaisesRegex(CheckoutError,'receipt'):
            self.ledger.finish_delivery(1,claimed['lease_token'],receipt_id='bad')
        self.assertEqual(self.ledger.delivery_backlog(),{'leased':1})

    def test_failure_is_queued_and_exponential_retry(self):
        self.settle()
        a=self.ledger.claim_delivery(now_ms=ISSUED+100000)
        self.ledger.finish_delivery(1,a['lease_token'],error='timeout',now_ms=ISSUED+100000)
        self.assertIsNone(self.ledger.claim_delivery(now_ms=ISSUED+110000))
        b=self.ledger.claim_delivery(now_ms=ISSUED+120000)
        self.assertEqual(b['event_id'],a['event_id'])
        self.ledger.finish_delivery(1,b['lease_token'],error='timeout',now_ms=ISSUED+120000)
        self.assertIsNone(self.ledger.claim_delivery(now_ms=ISSUED+159999))
        self.assertIsNotNone(self.ledger.claim_delivery(now_ms=ISSUED+160000))

    def test_reopen_existing_database_retains_outbox(self):
        self.settle()
        another=InvoiceLedger(self.db);another.initialize()
        self.assertEqual(another.delivery_backlog(),{'queued':1})

    def test_outbox_not_leaked_to_public_pending(self):
        public=self.ledger.public_state(self.ledger.by_token(self.inv.token))
        self.assertFalse(public['payment_confirmed'])
        self.assertNotIn('lease_token',public)
        self.assertNotIn('event_id',public)

class TestStoreBridge(DbTest):
    def test_reject_unapproved_store_urls(self):
        for invalid in ['https://example.com/api/payments/tron/fulfill/',
                        'http://mojplaywin.com/api/payments/tron/fulfill/',
                        'https://mojplaywin.com@evil.org/api/payments/tron/fulfill/',
                        'https://mojplaywin.com/api/payments/tron/fulfill/?redirect=evil',
                        'https://mojplaywin.com:444/api/payments/tron/fulfill/',
                        'https://mojplaywin.com/api/payments/tron/other/']:
            with self.subTest(url=invalid),self.assertRaises(DeliveryUnavailable):validate_endpoint(invalid)
        self.assertEqual(validate_endpoint(DEST),DEST)

    def test_canonical_signature_matches_payload_and_event(self):
        self.settle();claim=self.ledger.claim_delivery()
        req=delivery_request(claim,endpoint=DEST,secret=SECRET)
        body=req.data
        expected=hmac.new(SECRET.encode(),body,hashlib.sha256).hexdigest()
        self.assertEqual(req.get_header('X-mpw-event-signature'),'v1='+expected)
        self.assertEqual(json.loads(body)['order_id'],self.inv.order_id)
        self.assertEqual(json.loads(body)['txid'],TX)
        self.assertNotIn('lease_token',body.decode())

    def test_weak_signing_key_rejected(self):
        self.settle();claim=self.ledger.claim_delivery()
        with self.assertRaises(DeliveryUnavailable):delivery_request(claim,endpoint=DEST,secret='short')

    def test_unsigned_or_unknown_payment_denied(self):
        with self.assertRaises(DeliveryUnavailable):payload_for({'txid':TX})

    def test_receipt_200_wrong_id_cannot_release_product(self):
        self.settle()
        counts = drain_outbox(self.ledger,endpoint=DEST,secret=SECRET,limit=1,
            deliver=lambda e,**kw: 'invalid')
        self.assertEqual(counts['retried'],1)
        self.assertEqual(self.ledger.delivery_backlog(),{'queued':1})

    def test_delivery_200_with_matching_receipt(self):
        self.settle();call=[]
        def deliver(e,**kw):
            call.append(e['event_id'])
            return 'receipt-verified-101'
        counts=drain_outbox(self.ledger,endpoint=DEST,secret=SECRET,deliver=deliver)
        self.assertEqual(counts['delivered'],1)
        self.assertEqual(self.ledger.delivery_backlog(),{'delivered':1})
        self.assertEqual(drain_outbox(self.ledger,endpoint=DEST,secret=SECRET,deliver=deliver)['attempted'],0)
        self.assertEqual(len(call),1)

    def test_unknown_ack_retries_same_event_id(self):
        self.settle(); received=[]
        def fake(e,**kw):
            received.append(e['event_id'])
            if len(received)==1:raise DeliveryUnavailable('unknown result')
            return 'delivered-abc123'
        first=drain_outbox(self.ledger,endpoint=DEST,secret=SECRET,deliver=fake,now_ms=ISSUED+10000)
        self.assertEqual(first['retried'],1)
        second=drain_outbox(self.ledger,endpoint=DEST,secret=SECRET,deliver=fake,now_ms=ISSUED+29999)
        self.assertEqual(second['attempted'],0)
        third=drain_outbox(self.ledger,endpoint=DEST,secret=SECRET,deliver=fake,now_ms=ISSUED+30000)
        self.assertEqual(third['delivered'],1)
        self.assertEqual(received[0],received[1])

    def test_http_200_without_matching_ack_cannot_confirm(self):
        self.settle();e=self.ledger.claim_delivery()
        class FakeResponse:
            status=200
            headers={'Content-Type':'application/json'}
            def __init__(self,data):self.data=data
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n):return json.dumps(self.data).encode()
        for bad in ({'status':'pending','event_id':e['event_id'],'order_id':e['merchant_order_id'],'delivery_id':'receipt-10000'},
                    {'status':'delivered','event_id':'forged','order_id':e['merchant_order_id'],'delivery_id':'receipt-10000'},
                    {'status':'delivered','event_id':e['event_id'],'order_id':'wrong','delivery_id':'receipt-10000'}):
            with self.assertRaises(DeliveryUnavailable):
                send_to_store(e,endpoint=DEST,secret=SECRET,opener=lambda request,timeout:FakeResponse(bad))

    def test_valid_store_receipt_parses(self):
        self.settle();e=self.ledger.claim_delivery()
        class FakeResponse:
            status=200
            headers={'Content-Type':'application/json'}
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n):return json.dumps({'status':'delivered','event_id':e['event_id'],
                'order_id':e['merchant_order_id'],'delivery_id':'receipt-order-0001'}).encode()
        self.assertEqual(send_to_store(e,endpoint=DEST,secret=SECRET,opener=lambda request,timeout:FakeResponse()),'receipt-order-0001')

class TestVerifiedMerchantReceiver(DbTest):
    def test_exact_hmac_and_entitlement_delivery_contract(self):
        self.settle()
        deliveries={}
        def merchant(e,**kw):
            request=delivery_request(e,endpoint=DEST,secret=SECRET)
            parsed=verify_store_event(request.data,request.get_header('X-mpw-event-signature'),SECRET)
            self.assertEqual(parsed['order_id'],self.inv.order_id)
            self.assertEqual(parsed['amount_sun'],SUN)
            # Actual store must use its own atomic DB transaction + UNIQUE order/event.
            deliveries.setdefault(parsed['order_id'],parsed['event_id'])
            return 'receipt-merchant-123456'
        counts=drain_outbox(self.ledger,endpoint=DEST,secret=SECRET,deliver=merchant)
        self.assertEqual(counts['delivered'],1)
        self.assertEqual(len(deliveries),1)
        self.assertEqual(self.ledger.public_state(self.ledger.by_token(self.inv.token))['fulfillment'],'delivered')

    def test_receiver_rejects_forged_hmac(self):
        self.settle();e=self.ledger.claim_delivery()
        req=delivery_request(e,endpoint=DEST,secret=SECRET)
        with self.assertRaises(DeliveryUnavailable):verify_store_event(req.data,'v1'+'0'*64,SECRET)

    def test_receiver_rejects_modified_payment_amount(self):
        self.settle();e=self.ledger.claim_delivery()
        req=delivery_request(e,endpoint=DEST,secret=SECRET)
        modified=json.loads(req.data)
        modified['amount_sun']-=1
        with self.assertRaises(DeliveryUnavailable):verify_store_event(json.dumps(modified).encode(),req.get_header('X-mpw-event-signature'),SECRET)

    def test_receiver_rejects_duplicate_json_keys_even_if_signed(self):
        raw=b'{"event_id":"evil","event_id":"evilagain"}'
        sign='v1='+hmac.new(SECRET.encode(),raw,hashlib.sha256).hexdigest()
        with self.assertRaises(DeliveryUnavailable):verify_store_event(raw,sign,SECRET)

    def test_receiver_rejects_non_native_tron_asset(self):
        self.settle();e=self.ledger.claim_delivery()
        data=payload_for(e);data['currency']='USDT'
        raw=json.dumps(data).encode()
        sign='v1='+hmac.new(SECRET.encode(),raw,hashlib.sha256).hexdigest()
        with self.assertRaises(DeliveryUnavailable):verify_store_event(raw,sign,SECRET)

    def test_full_automatic_scanner_to_paid_to_delivery_one_run(self):
        store={}
        def recon(ledger,*,max_invoices,api_key):
            return reconcile_pending(ledger,max_invoices=max_invoices,api_key=api_key,
                discover=lambda address,issued,expires,api_key:[TX],
                fetch=lambda txid,api_key:records())
        def fulfill(ledger,*,endpoint,secret,limit):
            def fake_merchant(e,**kw):
                req=delivery_request(e,endpoint=endpoint,secret=secret)
                signed=verify_store_event(req.data,req.get_header('X-mpw-event-signature'),secret)
                # Reference only: actual Django order integration is NOT installed.
                store.setdefault(signed['order_id'],signed['event_id'])
                return 'receipt-delivered-987654'
            return drain_outbox(ledger,endpoint=endpoint,secret=secret,limit=limit,deliver=fake_merchant)
        counts=scan_once(str(self.db),str(self.db.parent/'scan.lock'),
            reconcile=recon,deliver=fulfill,store_endpoint=DEST,store_secret=SECRET)
        self.assertEqual(counts['settled'],1)
        self.assertEqual(counts['delivery_completed'],1)
        self.assertEqual(self.ledger.public_state(self.ledger.by_token(self.inv.token))['fulfillment'],'delivered')
        self.assertEqual(len(store),1)

class TestScannerFairness(DbTest):
    def test_due_cursor_rotates_without_starving_new_invoices(self):
        self.ledger.add_public_address(A2)
        next_invoice=self.ledger.issue(merchant_order_id='MPW-ORDER-AUTOTEST-2',product_title='Game',
            usd='4.00',usd_per_trx='0.32',now_ms=ISSUED+1000)
        self.assertEqual(self.ledger.pending(limit=1,now_ms=ISSUED+1001)[0]['merchant_order_id'],self.inv.order_id)
        self.ledger.defer_scan(1,now_ms=ISSUED+1001)
        self.assertEqual(self.ledger.pending(limit=1,now_ms=ISSUED+1001)[0]['merchant_order_id'],next_invoice.order_id)

    def test_malformed_mainnet_response_doesnt_crash_worker(self):
        def broken(txid,api_key):raise CheckoutError('RPC offline')
        scan=reconcile_pending(self.ledger,
               discover=lambda addr,issued,expires,api_key:[TX],fetch=broken)
        self.assertEqual(scan['failed_scans'],1)
        self.assertEqual(self.ledger.by_token(self.inv.token)['status'],'pending')

    def test_failed_indexer_defers_one_invoice_not_all(self):
        self.ledger.add_public_address(A2)
        nxt=self.ledger.issue(merchant_order_id='MPW-ORDER-AUTOTEST-2',product_title='Game',
                    usd='4.00',usd_per_trx='0.32',now_ms=ISSUED)
        def discover(addr,issued,expires,api_key):
            if addr==A1:raise CheckoutError('discovery offline')
            return []
        scan=reconcile_pending(self.ledger,discover=discover)
        self.assertEqual(scan['scanned'],2)
        self.assertEqual(scan['failed_scans'],1)

    def test_scanner_and_delivery_are_orchestrated_in_same_locked_run(self):
        self.settle()
        called=[]
        counts=scan_once(str(self.db),str(self.db.parent/'scan.lock'),
            reconcile=lambda led,max_invoices,api_key:{'scanned':0,'settled':0,'underpaid':0,'overpaid':0,'requires_review':0,'failed_scans':0},
            deliver=lambda led,endpoint,secret,limit:(called.append('deliver') or {'attempted':1,'delivered':1,'retried':0}),
            store_endpoint=DEST,store_secret=SECRET)
        self.assertEqual(called,['deliver'])
        self.assertTrue(counts['delivery_configured'])
        self.assertEqual(counts['delivery_completed'],1)

if __name__=='__main__':unittest.main()