"""Read-only unit checks: no TRX transfers, network calls, or production DB writes."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest import TestCase

from services.mpw_walletless_commercial_intent import (
    reserved_for_living_cities,
    LC_RESERVED_MIN_SUN, LC_RESERVED_MAX_SUN, SUN_PER_TRX,
)
from services.mpw_trx_walletless_core import issue_intent


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
