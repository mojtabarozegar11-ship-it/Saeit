"""Read-only unit checks: no TRX transfers, network calls, or production DB writes."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import os
from decimal import Decimal
from unittest import TestCase

from services.mpw_walletless_commercial_intent import (
    reserved_for_living_cities, require_active_merchant_wallet,
    LC_RESERVED_MIN_SUN, LC_RESERVED_MAX_SUN, SUN_PER_TRX,
)
from services.mpw_trx_walletless_core import issue_intent, PaymentHold


class SharedMerchantWalletAmountNamespaceTests(TestCase):
    def test_existing_and_future_whole_trx_game_products_are_reserved(self):
        for base_trx in (5, 7, 9, 12, 24, 48, 100, 500):
            for suffix in (LC_RESERVED_MIN_SUN, 42_123, LC_RESERVED_MAX_SUN):
                self.assertTrue(reserved_for_living_cities(base_trx * SUN_PER_TRX + suffix))

    def test_storefront_namespace_excludes_both_boundaries(self):
        for base_trx in (5, 7, 48):
            for suffix in (0, 999, 100_000, 999_999):
                self.assertFalse(reserved_for_living_cities(base_trx * SUN_PER_TRX + suffix))
        self.assertFalse(reserved_for_living_cities("5001000"))
        self.assertFalse(reserved_for_living_cities(-1))

    def test_core_invoice_allocator_skips_reserved_lc_amount(self):
        now = datetime.now(timezone.utc)
        random_choices = iter((1_500, 999))
        invoice = issue_intent(
            order_id=1, customer_id=1,
            recipient="THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73",
            usd_total=Decimal("5"), usd_per_trx=Decimal("1"),
            quote_observed_at=now, now=now,
            is_amount_reserved=reserved_for_living_cities,
            random_below=lambda _: next(random_choices),
        )
        self.assertEqual(invoice.amount_sun, 5_000_999)
        self.assertFalse(reserved_for_living_cities(invoice.amount_sun))


class MerchantActivationIssuanceGateTests(TestCase):
    """No network, no transfer, no production ledger writes."""

    receiver = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"

    def _report(self, current):
        return {
            "checked_at_utc": current.isoformat(),
            "first_positive_utc": (current - timedelta(minutes=11)).isoformat(),
            "status": "WALLET_ACTIVE_REVIEW_REQUIRED",
            "receiver_address": self.receiver,
            "receiver_configured": True,
            "full_rpc_reachable": True,
            "solid_rpc_reachable": True,
            "full_wallet_active": True,
            "solid_wallet_active": True,
            "incoming_index_ready": True,
            "main_gateway_authorized": True,
            "merchant_checkout_enabled": False,
        }

    def test_manual_review_and_independent_full_solid_proof_both_required(self):
        now = datetime.now(timezone.utc)
        with TemporaryDirectory() as directory:
            path = Path(directory, "wallet-readiness.json")
            data = self._report(now)
            path.write_text(json.dumps(data), encoding="utf8")
            os.chmod(path, 0o600)
            pending = SimpleNamespace(MPW_WALLETLESS_TRX_ACTIVATION_REVIEW_APPROVED=False)
            approved = SimpleNamespace(MPW_WALLETLESS_TRX_ACTIVATION_REVIEW_APPROVED=True)
            with self.assertRaises(PaymentHold):
                require_active_merchant_wallet(pending, self.receiver, report_path=str(path), now=now)
            require_active_merchant_wallet(approved, self.receiver, report_path=str(path), now=now)
            for field in ("full_wallet_active", "solid_wallet_active", "incoming_index_ready",
                          "main_gateway_authorized"):
                invalid = dict(data, **{field: False})
                path.write_text(json.dumps(invalid), encoding="utf8")
                with self.assertRaises(PaymentHold, msg=field):
                    require_active_merchant_wallet(approved, self.receiver, report_path=str(path), now=now)
            path.write_text(json.dumps(data), encoding="utf8")
            with self.assertRaises(PaymentHold):
                require_active_merchant_wallet(approved, "TWrongReceiver", report_path=str(path), now=now)
            data["checked_at_utc"] = (now - timedelta(hours=1)).isoformat()
            path.write_text(json.dumps(data), encoding="utf8")
            with self.assertRaises(PaymentHold):
                require_active_merchant_wallet(approved, self.receiver, report_path=str(path), now=now)
            os.chmod(path, 0o644)
            with self.assertRaises(PaymentHold):
                require_active_merchant_wallet(approved, self.receiver, report_path=str(path), now=now)
