"""Astra research intake tests: never convert draft/evidence to market demand."""
import io
import json

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.models import (
    Product, FactoryRun, ResearchProject, ResearchSource, Evidence,
    FactoryQueueItem,
)


@override_settings(SAEIT_ENV="ci")
class PrivateLegacyIntakeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="astra-fake-test-user", password="fake-test-password"
        )
        # bulk_create skips the original Product/FactoryRun governance save
        # hooks; this is isolated fictional data in Django test SQLite only.
        self.draft, self.public, self.unmanaged = Product.objects.bulk_create([
            Product(title="Synthetic unpublished factory draft",
                    product_type="digital", factory_managed=True, active=False),
            Product(title="Already published synthetic", product_type="digital",
                    factory_managed=False, active=True),
            Product(title="Unrelated storefront item", product_type="digital",
                    factory_managed=False, active=False),
        ])
        # Synthetic test-only lifecycle fixture: mark an already-active
        # unrelated record as factory-owned *after* creation. This never
        # grants activation and preserves the production activation guard.
        Product.objects.filter(pk=self.public.pk).update(factory_managed=True)
        self.public.refresh_from_db()

    def invoke(self, **kwargs):
        output=io.StringIO()
        call_command("astra_private_research_intake", stdout=output, **kwargs)
        return json.loads(output.getvalue().splitlines()[-1])

    def test_read_only_is_default_and_order_free(self):
        result=self.invoke()
        self.assertEqual(result["mode"],"READ_ONLY_PREVIEW")
        self.assertEqual(result["scanned"],1)
        self.assertFalse(result["customer_orders_needed"])
        self.assertEqual(result["commercially_qualified_products"],0)
        self.assertEqual(FactoryQueueItem.objects.count(),0)

    def test_private_draft_creates_one_uncharged_research_task(self):
        report=self.invoke(apply_private=True)
        self.assertEqual(report["new_research_tasks"],1)
        row=FactoryQueueItem.objects.get()
        self.assertEqual(row.key,f"legacy-factory-product:{self.draft.pk}")
        self.assertEqual(row.stage,"WAITING_FOR_EVIDENCE")
        self.assertFalse(row.market_demand_verified)
        self.assertFalse(row.publication_allowed)
        self.assertIsNone(row.commercial_quality_score)
        self.assertEqual(row.record["source_reference_count_unverified"],0)
        self.assertEqual(row.record["linked_evidence_row_count_unverified"],0)

    def test_repeated_tick_is_idempotent(self):
        self.invoke(apply_private=True)
        report=self.invoke(apply_private=True)
        self.assertEqual(report["new_research_tasks"],0)
        self.assertEqual(report["unchanged_research_tasks"],1)
        self.assertEqual(FactoryQueueItem.objects.count(),1)

    def test_research_citations_still_do_not_prove_demand(self):
        run=FactoryRun.objects.bulk_create([
            FactoryRun(run_id="synthetic-legacy-001", product=self.draft,
                       goal="Fictional farm review", environment="ci")
        ])[0]
        project=ResearchProject.objects.bulk_create([
            ResearchProject(title="Synthetic project", objective="Fake data",
                            owner=self.user, factory_run=run)
        ])[0]
        source=ResearchSource.objects.bulk_create([
            ResearchSource(project=project,title="Illustrative",
                           url="https://example.org/test",
                           content_hash="0"*64)
        ])[0]
        Evidence.objects.bulk_create([
            Evidence(project=project,source=source,
                     passage="Unverified fictional text")
        ])
        result=self.invoke(apply_private=True)
        self.assertEqual(result["new_research_tasks"],1)
        row=FactoryQueueItem.objects.get()
        self.assertEqual(row.record["source_reference_count_unverified"],1)
        self.assertEqual(row.record["linked_evidence_row_count_unverified"],1)
        self.assertFalse(row.market_demand_verified)
        self.assertEqual(result["new_products_for_sale"],0)

    def test_cannot_overwrite_reviewed_item(self):
        self.invoke(apply_private=True)
        row=FactoryQueueItem.objects.get()
        row.stage="REVIEW_REQUIRED"
        row.save(update_fields=["stage"])
        report=self.invoke(apply_private=True)
        row.refresh_from_db()
        self.assertEqual(row.stage,"REVIEW_REQUIRED")
        self.assertEqual(report["updated_research_tasks"],0)

    def test_limit_and_cursor_are_bounded(self):
        self.assertEqual(self.invoke(after_id=self.draft.pk)["scanned"],0)
        for kwargs in ({"limit":0},{"limit":101},{"after_id":-1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(CommandError):
                self.invoke(**kwargs)

    @override_settings(SAEIT_ENV="production")
    def test_write_forbidden_on_production_even_for_private_switch(self):
        with self.assertRaisesRegex(CommandError,"WRITE_BLOCKED"):
            self.invoke(apply_private=True)
        self.assertEqual(FactoryQueueItem.objects.count(),0)

    @override_settings(SAEIT_ENV="production")
    def test_dry_run_remains_read_only_in_production(self):
        self.assertEqual(self.invoke()["scanned"],1)
        self.assertEqual(FactoryQueueItem.objects.count(),0)

    def test_no_order_or_payment_side_effects(self):
        out=self.invoke(apply_private=True)
        self.assertEqual(out["network_calls"],0)
        self.assertFalse(out["stage45_auto_publishing"])
        self.assertFalse(out["payment_activated"])
        self.assertEqual(out["new_products_for_sale"],0)
        self.public.refresh_from_db()
        self.unmanaged.refresh_from_db()
        self.assertTrue(self.public.active)
        self.assertFalse(self.unmanaged.factory_managed)
