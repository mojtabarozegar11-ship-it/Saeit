"""Staging diagnostic command smoke tests (no external network)."""
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from core.models import Product


class Stage4DiagnosticsTests(TestCase):
    @override_settings(SAEIT_ENV="production")
    def test_production_refused(self):
        with self.assertRaises(CommandError):
            call_command("factory_stage4_diagnostics", stdout=StringIO())

    @override_settings(SAEIT_ENV="staging")
    def test_counts_persisted_blockers_without_mutation(self):
        Product.objects.create(
            title="Exhausted", product_type="digital",
            metadata={"factory_state": "needs_research",
                      "validation": {"stage4_research": {"status": "capacity_exhausted"}}},
        )
        Product.objects.create(
            title="Retry", product_type="digital",
            metadata={"factory_state": "needs_research",
                      "validation": {"stage4_research": {"status": "retry_scheduled"}}},
        )
        out = StringIO()
        call_command("factory_stage4_diagnostics", stdout=out)
        report = out.getvalue()
        self.assertIn("STAGE4_PRODUCTS_WAITING=2", report)
        self.assertIn("STAGE4_CAPACITY_EXHAUSTED=1", report)
        self.assertIn("STAGE4_RETRY_PENDING=1", report)
        self.assertIn("STAGE4_DIAGNOSTIC_ONLY", report)
        self.assertEqual(Product.objects.count(), 2)
