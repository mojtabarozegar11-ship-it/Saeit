"""Internal native TRX quote math: no live wallet, buyer or invoice writes."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.test import SimpleTestCase

from core.tron_tenant_policy import (
    CANONICAL_ASSET, CANONICAL_CHAIN, REQUIRED_ATTESTATIONS, registered_scope,
)
from core.tron_quote_contract import (
    NativeTrxQuoteError, make_native_trx_quote, verify_native_trx_quote,
)

KEY = b"completely-test-only-private-quote-key-over-thirty-two-bytes"
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
REGISTRY = {
    ("mojplaywin.com", "saman"): {
        "tenant_id": "signal_saman", "network": CANONICAL_CHAIN,
        "asset": CANONICAL_ASSET,
        **{name: True for name in REQUIRED_ATTESTATIONS},
    },
    ("mojplaywin.com", "moj_prop"): {
        "tenant_id": "moj_prop", "network": CANONICAL_CHAIN,
        "asset": CANONICAL_ASSET,
        **{name: True for name in REQUIRED_ATTESTATIONS},
    },
}


class NativeTrxQuoteContractTests(SimpleTestCase):
    def quote(self, **changes):
        args = {
            "tenant": registered_scope(host="mojplaywin.com", brand="saman", registry=REGISTRY),
            "merchant_registry": REGISTRY,
            "order_id": "order-10001",
            "sku": "moj-signals-standard",
            "usd_price": "12",
            "trx_usd_rate": "0.25",
            "observed_at_utc": NOW,
            "expires_at_utc": NOW + timedelta(minutes=3),
            "signing_key": KEY,
            "now_utc": NOW,
            "trusted_order_registry": {
                "order-10001": {
                    "tenant_id": "signal_saman",
                    "sku": "moj-signals-standard",
                    "usd_price": "12",
                    "payment_state": "pending",
                    "cancelled": False,
                    "expires_at_utc": NOW + timedelta(minutes=10),
                },
            },
        }
        args.update(changes)
        return make_native_trx_quote(**args)

    def valid(self, *, quote=None, **changes):
        data = {
            "quote": self.quote() if quote is None else quote,
            "merchant_registry": REGISTRY,
            "now_utc": NOW + timedelta(minutes=1),
            "signing_key": KEY,
            "trusted_order_registry": {
                "order-10001": {
                    "tenant_id": "signal_saman",
                    "sku": "moj-signals-standard",
                    "usd_price": "12",
                    "payment_state": "pending",
                    "cancelled": False,
                    "expires_at_utc": NOW + timedelta(minutes=10),
                },
            },
        }
        data.update(changes)
        return verify_native_trx_quote(**data)

    def test_exact_integer_sun_for_valid_tenant_quote(self):
        q = self.quote()
        self.assertEqual(q.exact_amount_sun, 48_000_000)
        self.assertEqual(q.tenant_id, "signal_saman")
        self.assertTrue(self.valid(quote=q))

    def test_round_ceiling_prevents_sub_sun_price_and_truncation(self):
        q = self.quote(
            usd_price="0.0000001", trx_usd_rate="1",
            trusted_order_registry={"order-10001": {
                "tenant_id": "signal_saman", "sku": "moj-signals-standard",
                "usd_price": "0.0000001", "payment_state": "pending",
                "cancelled": False,
                "expires_at_utc": NOW + timedelta(minutes=10),
            }},
        )
        self.assertEqual(q.exact_amount_sun, 1)
        self.assertTrue(self.valid(quote=q, trusted_order_registry={"order-10001": {
            "tenant_id": "signal_saman", "sku": "moj-signals-standard",
            "usd_price": "0.0000001", "payment_state": "pending", "cancelled": False,
            "expires_at_utc": NOW + timedelta(minutes=10),
        }}))

    def test_quote_cannot_be_reused_for_different_sku_or_order(self):
        q = self.quote()
        self.assertFalse(self.valid(quote=replace(q, sku="moj-signals-professional")))
        self.assertFalse(self.valid(quote=replace(q, order_id="order-10002")))

    def test_quote_cannot_be_reused_across_merchant_brand(self):
        q = self.quote()
        self.assertFalse(self.valid(quote=replace(q, brand="moj_prop")))
        self.assertFalse(self.valid(quote=replace(q, tenant_id="moj_prop")))

    def test_quote_is_rejected_after_expiry_or_before_rate_observation(self):
        q = self.quote()
        self.assertFalse(self.valid(quote=q, now_utc=NOW + timedelta(minutes=3)))
        self.assertFalse(self.valid(quote=q, now_utc=NOW - timedelta(seconds=1)))

    def test_quote_hmac_is_bound_to_amount_and_rate(self):
        q = self.quote()
        self.assertFalse(self.valid(quote=replace(q, exact_amount_sun=1)))
        self.assertFalse(self.valid(quote=replace(q, trx_usd_rate="1")))

    def test_merchant_revocation_blocks_old_signed_quote(self):
        disabled = {
            **REGISTRY,
            ("mojplaywin.com", "saman"): {
                **REGISTRY[("mojplaywin.com", "saman")],
                "merchant_identity_approved": False,
            },
        }
        self.assertFalse(self.valid(merchant_registry=disabled))

    def test_missing_registry_cannot_issue_quote(self):
        with self.assertRaises(NativeTrxQuoteError):
            self.quote(merchant_registry={})
        with self.assertRaises(NativeTrxQuoteError):
            self.quote(merchant_registry=None)

    def test_float_and_boolean_money_rejected(self):
        for money in (1.25, True, "NaN", "Infinity", "-1", "0"):
            with self.subTest(money=money), self.assertRaises(NativeTrxQuoteError):
                self.quote(usd_price=money)

    def test_unbounded_rate_and_stale_quote_rejected(self):
        for rate in ("0.00000001", "10001", "0"):
            with self.subTest(rate=rate), self.assertRaises(NativeTrxQuoteError):
                self.quote(trx_usd_rate=rate)
        with self.assertRaises(NativeTrxQuoteError):
            self.quote(expires_at_utc=NOW + timedelta(minutes=12))

    def test_tampered_signature_and_key_rotation_rejected(self):
        q = self.quote()
        self.assertFalse(self.valid(quote=replace(q, signature="f" * 64)))
        self.assertFalse(self.valid(quote=q, signing_key=b"another-test-only-secret-over-thirty-two-bytes"))

    def test_invalid_or_lookalike_sku_order_ref_rejected(self):
        for order, sku in (("../bad", "moj-signals-plus"),
                           ("order-10001", "invalid sku"),
                           ("order-10001", "foo/../../bar")):
            with self.subTest(order=order, sku=sku), self.assertRaises(NativeTrxQuoteError):
                self.quote(order_id=order, sku=sku)

    def test_non_utc_time_does_not_authorize_quote(self):
        with self.assertRaises(NativeTrxQuoteError):
            self.quote(observed_at_utc=datetime(2026, 11, 15))
        self.assertFalse(self.valid(now_utc=datetime(2026, 11, 15)))

    def test_future_dated_exchange_rate_rejected_at_quote_creation(self):
        with self.assertRaisesRegex(NativeTrxQuoteError, "exchange_rate_expired"):
            self.quote(observed_at_utc=NOW + timedelta(seconds=1),
                       expires_at_utc=NOW + timedelta(minutes=3))

    def test_stale_oracle_rate_rejected_even_if_quote_expiry_is_future(self):
        with self.assertRaisesRegex(NativeTrxQuoteError, "exchange_rate_expired"):
            self.quote(observed_at_utc=NOW - timedelta(minutes=5, seconds=1),
                       expires_at_utc=NOW + timedelta(minutes=1))

    def test_server_issuance_time_is_required_and_utc(self):
        with self.assertRaises(NativeTrxQuoteError):
            self.quote(now_utc=datetime(2026, 11, 15))
        with self.assertRaisesRegex(NativeTrxQuoteError, "exchange_rate_expired"):
            self.quote(now_utc=NOW + timedelta(minutes=3))

    def test_missing_or_forged_server_order_refuses_quote(self):
        for record in (None, "approved", True, {}, {"order-10001": "fake"}):
            with self.subTest(record=repr(record)), self.assertRaisesRegex(
                NativeTrxQuoteError, "trusted_order_missing_or_mismatched"
            ):
                self.quote(trusted_order_registry=record)

    def test_quote_must_match_server_order_price_tenant_sku_and_unpaid_state(self):
        changes = (
            {"tenant_id": "other_tenant"}, {"sku": "other_sku"},
            {"usd_price": "0.01"}, {"payment_state": "paid"},
            {"payment_state": "cancelled"}, {"cancelled": True},
        )
        for corrupted in changes:
            with self.subTest(corrupted=corrupted), self.assertRaisesRegex(
                NativeTrxQuoteError, "trusted_order_missing_or_mismatched"
            ):
                self.quote(trusted_order_registry={"order-10001": {
                    "tenant_id": "signal_saman", "sku": "moj-signals-standard",
                    "usd_price": "12", "payment_state": "pending",
                    "cancelled": False, "expires_at_utc": NOW + timedelta(minutes=10),
                    **corrupted
                }})

    def test_cancellation_in_live_order_registry_invalidates_old_quote(self):
        record = {"tenant_id": "signal_saman", "sku": "moj-signals-standard",
                  "usd_price": "12", "payment_state": "pending", "cancelled": True}
        self.assertFalse(self.valid(trusted_order_registry={"order-10001": record}))

    def test_pending_order_without_future_utc_deadline_cannot_be_quoted(self):
        base = {
            "tenant_id": "signal_saman", "sku": "moj-signals-standard",
            "usd_price": "12", "payment_state": "pending", "cancelled": False,
        }
        for expires in (None, NOW, NOW - timedelta(seconds=1),
                        datetime(2026, 11, 15, 12, 10)):
            with self.subTest(expires=repr(expires)), self.assertRaisesRegex(
                NativeTrxQuoteError, "trusted_order_missing_or_mismatched"
            ):
                self.quote(trusted_order_registry={
                    "order-10001": {**base, "expires_at_utc": expires}
                })

    def test_order_can_expire_before_signature_quote_does(self):
        record = {
            "tenant_id": "signal_saman", "sku": "moj-signals-standard",
            "usd_price": "12", "payment_state": "pending", "cancelled": False,
            "expires_at_utc": NOW + timedelta(minutes=2),
        }
        q = self.quote(
            expires_at_utc=NOW + timedelta(minutes=4),
            trusted_order_registry={"order-10001": record},
        )
        self.assertTrue(self.valid(
            quote=q, now_utc=NOW + timedelta(minutes=1),
            trusted_order_registry={"order-10001": record},
        ))
        self.assertFalse(self.valid(
            quote=q, now_utc=NOW + timedelta(minutes=3),
            trusted_order_registry={"order-10001": record},
        ))

    def test_invoice_or_receipt_never_created_by_quote_function(self):
        q = self.quote()
        self.assertFalse(hasattr(q, "paid"))
        self.assertFalse(hasattr(q, "receipt"))
        self.assertFalse(hasattr(q, "create_invoice"))
