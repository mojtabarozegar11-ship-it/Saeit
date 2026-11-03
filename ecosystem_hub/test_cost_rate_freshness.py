"""Fail-closed production pricing regressions; no real orders or payments."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from enterprise_portal.models import BusinessUnit, InventoryItem, JournalEntry, StockMovement
from .costing import estimate_manufacturing_cost
from .models import (
    BillOfMaterials, MaterialRequirement, MaterialPriceReference,
    ProductionCostScenario, ProductionOrder,
)


class CostRateFreshnessTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.owner = get_user_model().objects.create_superuser(
            username="cost-freshness-owner", password="unused-test-only",
        )
        self.unit = BusinessUnit.objects.create(code="cost-fresh", name="Cost Freshness")
        self.other_unit = BusinessUnit.objects.create(code="cost-other", name="Other Unit")
        self.product = InventoryItem.objects.create(
            unit=self.unit, sku="FINAL", title="Finished product",
        )
        self.material = InventoryItem.objects.create(
            unit=self.unit, sku="RAW", title="Raw input",
        )
        self.recipe = BillOfMaterials.objects.create(
            unit=self.unit, product=self.product, code="COST-FRESH-BOM",
            yield_quantity=Decimal("1"),
        )
        MaterialRequirement.objects.create(
            formula=self.recipe, item=self.material,
            quantity=Decimal("3"), scrap_percent=Decimal("0"),
        )
        self.order = ProductionOrder.objects.create(
            unit=self.unit, formula=self.recipe, code="COST-FRESH-ORDER",
            quantity=Decimal("2"), owner=self.owner,
        )
        self.scenario = ProductionCostScenario.objects.create(
            unit=self.unit, order=self.order, label="Evidence-limited estimate",
            currency="IRR", labor_estimate=Decimal("20"),
            overhead_estimate=Decimal("10"), prepared_by=self.owner,
        )

    def price(self, age, amount="5", *, unit=None, currency="IRR"):
        return MaterialPriceReference.objects.create(
            unit=unit or self.unit, item=self.material, currency=currency,
            amount=Decimal(amount), status="verified", recorded_by=self.owner,
            evidence_ref="supplier-quote-" + str(age),
            as_of=self.today - timedelta(days=age),
        )

    def test_expired_verified_rate_blocks_total_and_discloses_stale_sku(self):
        self.price(91)
        result = estimate_manufacturing_cost(self.scenario, as_of=self.today)
        self.assertFalse(result["complete"])
        self.assertEqual(result["missing_skus"], ["RAW"])
        self.assertEqual(result["stale_skus"], ["RAW"])
        self.assertEqual(result["max_rate_age_days"], 90)
        self.assertIsNone(result["components"][0]["rate"])
        self.assertIsNone(result["total"])
        self.assertIsNone(result["unit_cost"])
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(StockMovement.objects.exists())

    def test_boundary_rate_and_newer_quote_restore_estimate(self):
        self.price(90, "5")
        at_boundary = estimate_manufacturing_cost(self.scenario, as_of=self.today)
        self.assertTrue(at_boundary["complete"])
        self.assertEqual(at_boundary["total"], Decimal("60.00"))
        self.assertEqual(at_boundary["unit_cost"], Decimal("30.00"))
        self.assertEqual(at_boundary["stale_skus"], [])
        self.price(1, "7")
        latest = estimate_manufacturing_cost(self.scenario, as_of=self.today)
        self.assertEqual(latest["total"], Decimal("72.00"))
        self.assertEqual(latest["unit_cost"], Decimal("36.00"))
        self.assertEqual(latest["components"][0]["rate"], Decimal("7"))

    def test_wrong_currency_and_future_rate_never_rescue_expired_quote(self):
        self.price(91, "5")
        self.price(0, "99", currency="USD")
        MaterialPriceReference.objects.create(
            unit=self.unit, item=self.material, currency="IRR",
            amount=Decimal("99"), status="verified", recorded_by=self.owner,
            evidence_ref="future-price-not-yet-effective",
            as_of=self.today + timedelta(days=1),
        )
        result = estimate_manufacturing_cost(self.scenario, as_of=self.today)
        self.assertFalse(result["complete"])
        self.assertEqual(result["stale_skus"], ["RAW"])
        self.assertIsNone(result["total"])

    def test_invalid_rate_window_is_rejected_without_db_writes(self):
        for window in (0, -1, 3651, 90.0, True):
            with self.subTest(window=window):
                with self.assertRaises(ValueError):
                    estimate_manufacturing_cost(
                        self.scenario, as_of=self.today, max_rate_age_days=window,
                    )
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(StockMovement.objects.exists())
