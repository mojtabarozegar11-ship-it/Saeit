"""Release gating and two-source proof regression tests; no merchant funds."""
import copy
import unittest
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from services.mpw_trx_walletless_core import InvoiceIntent,PaymentHold
from services.mpw_walletless_commercial_intent import _commercial_db
from services.mpw_trx_commercial_web import _nocache
from services.mpw_trx_commercial_chain import read_only_independent_pair,PINNED
from services.mpw_tron_independent_solidified_rpc import hex_to_tron_address
from tests.test_mpw_tron_independent_solidified_rpc import (
    TX,HEX_TO,HEX_FROM,MS,tx_body,tx_info,
)

class ProductionCheckoutReleaseTests(unittest.TestCase):
    def test_private_checkout_allows_same_origin_csrf_referer_without_leaking_cross_origin(self):
        from django.http import HttpResponse
        response=_nocache(HttpResponse("form"))
        self.assertEqual(response["Referrer-Policy"],"same-origin")
        self.assertEqual(response["Cache-Control"],"private, no-store, max-age=0")

    def test_explicit_public_launch_does_not_claim_a_merchant_test_payment(self):
        config=SimpleNamespace(DEBUG=False, MPW_COMMERCE_RELEASE_READY=True,
            MPW_COMMERCE_DOWNLOADS_ENABLED=True, MPW_WALLETLESS_TRX_PUBLIC_ENABLED=True,
            MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=False,
            MPW_WALLETLESS_TRX_PUBLIC_RELEASE_AUTHORIZED=True)
        db=SimpleNamespace(vendor="mysql",alias="default")
        _commercial_db(config,db)
        self.assertFalse(config.MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED)
        for field in ('MPW_COMMERCE_DOWNLOADS_ENABLED','MPW_COMMERCE_RELEASE_READY',
                      'MPW_WALLETLESS_TRX_PUBLIC_ENABLED','MPW_WALLETLESS_TRX_PUBLIC_RELEASE_AUTHORIZED'):
            setattr(config,field,False)
            with self.subTest(field=field),self.assertRaises(PaymentHold):
                _commercial_db(config,db)
            setattr(config,field,True)

    def setUp(self):
        self.settings=SimpleNamespace(
            DEBUG=False,
            MPW_COMMERCE_RELEASE_READY=True,
            MPW_COMMERCE_DOWNLOADS_ENABLED=True,
            MPW_WALLETLESS_TRX_PUBLIC_ENABLED=True,
            MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=True,
        )
        self.database=SimpleNamespace(vendor="mysql",alias="default")

    def test_all_production_gates_required_for_any_sql_operation(self):
        _commercial_db(self.settings,self.database)
        for attribute,denied in (
            ("DEBUG",True),("MPW_COMMERCE_RELEASE_READY",False),
            ("MPW_COMMERCE_DOWNLOADS_ENABLED",False),
            ("MPW_WALLETLESS_TRX_PUBLIC_ENABLED",False),
            ("MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED",False),
        ):
            original=getattr(self.settings,attribute)
            setattr(self.settings,attribute,denied)
            try:
                with self.subTest(attribute=attribute),self.assertRaises(PaymentHold):
                    _commercial_db(self.settings,self.database)
            finally:
                setattr(self.settings,attribute,original)
        with self.assertRaises(PaymentHold):
            _commercial_db(self.settings,SimpleNamespace(vendor="sqlite",alias="default"))
        with self.assertRaises(PaymentHold):
            _commercial_db(self.settings,SimpleNamespace(vendor="mysql",alias="replica"))

    def test_solidified_mainnet_evidence_from_distinct_pinned_nodes(self):
        self.assertNotEqual(PINNED[0][1],PINNED[1][1])
        self.assertNotEqual(PINNED[0][0],PINNED[1][0])
        seen=[]
        def transport(provider,op,tx=""):
            seen.append((provider[0],op,tx))
            if op=="head":
                return {"block_header":{"raw_data":{"number":70000000}}}
            return copy.deepcopy(tx_body() if op=="body" else tx_info())
        with patch("services.mpw_trx_commercial_chain.get",side_effect=transport),patch(
            "services.mpw_trx_commercial_chain.head_height_and_age",return_value=70000000
        ):
            pair=read_only_independent_pair()
            when=datetime.fromtimestamp((MS-9000)/1000,timezone.utc)
            invoice=InvoiceIntent(
                order_id=2,customer_id=7,network="tron-mainnet",
                recipient=hex_to_tron_address(HEX_TO),amount_sun=123456,
                usd_total=Decimal("0.03"),quote_usd_per_trx=Decimal("0.25"),
                issued_at=when,expires_at=when+timedelta(minutes=10),
            )
            confirmed=pair.verify(invoice,TX,lambda *_:False)
            self.assertEqual(confirmed,(TX,hex_to_tron_address(HEX_FROM)))
            self.assertEqual(len(seen),6)
            self.assertEqual(seen[0][1:3],("head",""))
            self.assertEqual(seen[2][1:3],("body",TX))
            with self.assertRaises(PaymentHold):
                pair.verify(invoice,TX,lambda *_:True)

    def test_bad_or_stale_read_proofs_block_commercial_settlement(self):
        with patch("services.mpw_trx_commercial_chain.get",side_effect=OSError("offline")):
            with self.assertRaises(PaymentHold):
                read_only_independent_pair()
        with patch("services.mpw_trx_commercial_chain.get",return_value={}),patch(
            "services.mpw_trx_commercial_chain.head_height_and_age",
            side_effect=[70000000,70001001]
        ):
            with self.assertRaises(PaymentHold):
                read_only_independent_pair()

if __name__=="__main__":
    unittest.main()
