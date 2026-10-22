import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.mpw_trx_walletless_core import (
    NETWORK, InvoiceIntent, PaymentHold, SolidifiedTransfer,
    issue_intent, verify_two_source_transfer
)
T0=datetime(2026,10,22,0,0,tzinfo=timezone.utc)
ADDRESS='T'+'A'*33
SENDER='T'+'B'*33
TX='a'*64

def make_intent(**kwargs):
    args=dict(
        order_id=12,customer_id=43,recipient=ADDRESS,usd_total=Decimal('0.03'),
        usd_per_trx=Decimal('0.30'),quote_observed_at=T0-timedelta(seconds=8),
        now=T0,is_amount_reserved=lambda amt:False,random_below=lambda hi:0)
    args.update(kwargs)
    return issue_intent(**args)

def make_proof(intent,source='rpc-a',**kwargs):
    args=dict(source_id=source,tx_hash=TX,network=NETWORK,recipient=intent.recipient,
      sender=SENDER,amount_sun=intent.amount_sun,
      block_time=intent.issued_at+timedelta(minutes=1),solidified=True,
      transfer_contract=True,execution_success=True)
    args.update(kwargs)
    return SolidifiedTransfer(**args)


class WalletlessTrxKernelTests(unittest.TestCase):
    def setUp(self):
        self.inv=make_intent()
        self.p=make_proof(self.inv)
        self.q=make_proof(self.inv,source='rpc-b')

    def good(self,a=None,b=None,used=None):
        return verify_two_source_transfer(
            self.inv,a or self.p,b or self.q,
            tx_previously_consumed=used or (lambda network,tx:False))

    def denied(self,**changes):
        with self.assertRaises(PaymentHold):
            self.good(a=replace(self.p,**changes))

    def test_exact_unique_invoice_amount(self):
        self.assertEqual(self.inv.amount_sun,100000)
        self.assertEqual(self.inv.network,NETWORK)
        self.assertEqual(self.inv.expires_at-T0,timedelta(minutes=10))

    def test_pricing_precision(self):
        amt=make_intent(random_below=lambda hi:hi-1)
        self.assertLessEqual((Decimal(amt.amount_sun-100000)/Decimal(1_000_000))*Decimal('0.30'),Decimal('0.005'))

    def test_reserved_collision_moves_on(self):
        calls=[0]
        def rand(hi):
            out=calls[0]
            calls[0]+=1
            return out
        intent=make_intent(is_amount_reserved=lambda x:x==100000,random_below=rand)
        self.assertEqual(intent.amount_sun,100001)

    def test_exhaustion_fails_closed(self):
        with self.assertRaises(PaymentHold):
            make_intent(is_amount_reserved=lambda x:True)

    def test_stale_and_future_quote(self):
        for ts in (T0-timedelta(seconds=91),T0+timedelta(seconds=1)):
            with self.subTest(ts=ts),self.assertRaises(PaymentHold):
                make_intent(quote_observed_at=ts)

    def test_invalid_prices_and_buyer(self):
        for v in (Decimal('NaN'),Decimal('Infinity'),Decimal('0'),Decimal('-1'),1.0):
            with self.subTest(v=v),self.assertRaises(PaymentHold):
                make_intent(usd_total=v)
        with self.assertRaises(PaymentHold):
            make_intent(customer_id=None)

    def test_unsafe_entropy(self):
        for out in (-1,1.3,1000000000):
            with self.subTest(out=out),self.assertRaises(PaymentHold):
                make_intent(random_below=lambda hi:out)

    def test_valid_evidence(self):
        self.assertEqual(self.good(),(TX,SENDER))

    def test_single_source_denied(self):
        with self.assertRaises(PaymentHold):
            self.good(b=replace(self.q,source_id='rpc-a'))

    def test_double_spend_denied(self):
        with self.assertRaises(PaymentHold):
            self.good(used=lambda network,tx:True)

    def test_bad_network_or_destination(self):
        self.denied(network='tron-shasta')
        self.denied(recipient='T'+'C'*33)

    def test_wrong_amount_and_types(self):
        self.denied(amount_sun=self.inv.amount_sun-1)
        self.denied(amount_sun=self.inv.amount_sun+1)
        self.denied(amount_sun=str(self.inv.amount_sun))
        self.denied(amount_sun=True)

    def test_no_finality_or_wrong_type(self):
        self.denied(solidified=False)
        self.denied(solidified='true')
        self.denied(transfer_contract=False)
        self.denied(execution_success=False)

    def test_wrong_sender_or_hash(self):
        self.denied(sender='not-tron')
        self.denied(tx_hash='a'*63)
        with self.assertRaises(PaymentHold):
            self.good(b=replace(self.q,sender='T'+'C'*33))
        with self.assertRaises(PaymentHold):
            self.good(b=replace(self.q,tx_hash='c'*64))

    def test_time_window_inclusive(self):
        self.denied(block_time=T0-timedelta(seconds=1))
        self.denied(block_time=T0+timedelta(minutes=10,seconds=1))
        with self.assertRaises(PaymentHold):
            self.good(b=replace(self.q,block_time=T0+timedelta(seconds=7)))

    def test_untrusted_naive_timestamps(self):
        self.denied(block_time=datetime(2026,10,22))
        with self.assertRaises(PaymentHold):
            make_intent(quote_observed_at=datetime(2026,10,22))


if __name__=='__main__':
    unittest.main()
