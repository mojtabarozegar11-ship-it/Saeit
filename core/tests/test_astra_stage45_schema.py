"""Additive Stage45 schema tests; only an isolated test database is used."""
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from core.models import DiscoverySnapshot, FactoryQueueItem


class AstraStage45ResearchSchemaTests(TestCase):
    def test_new_queue_row_is_research_only_and_not_for_sale(self):
        job = FactoryQueueItem.objects.create(
            key="discovery:ASTRA-H001",
            kind="discovery",
        )
        self.assertEqual(job.status, "RESEARCH_REQUIRED")
        self.assertIsNone(job.priority_score)
        self.assertFalse(job.evidence_verified_independently)
        self.assertFalse(job.build_authorized)
        self.assertFalse(job.publish_authorized)
        self.assertFalse(job.payment_authorized)

    def test_snapshot_exact_queue_fk_and_unverified_claim_are_persisted(self):
        first = FactoryQueueItem.objects.create(key="discovery:ASTRA-H001")
        second = FactoryQueueItem.objects.create(key="discovery:ASTRA-H002")
        record = {"claim_type": "problem", "note": "unverified reference"}
        item = DiscoverySnapshot.objects.create(
            hypothesis=first,
            url="https://example.org/research",
            content_hash="a" * 64,
            retrieved_at=timezone.now(),
            record=record,
        )
        self.assertEqual(DiscoverySnapshot.objects.filter(hypothesis=first).count(), 1)
        self.assertEqual(DiscoverySnapshot.objects.filter(hypothesis=second).count(), 0)
        self.assertEqual(item.record, record)
        self.assertFalse(first.build_authorized)

    def test_untrusted_research_row_cannot_override_production_permissions(self):
        job = FactoryQueueItem.objects.create(key="discovery:ASTRA-H003")
        for field in (
            "evidence_verified_independently",
            "build_authorized",
            "publish_authorized",
            "payment_authorized",
        ):
            with self.subTest(field=field):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        FactoryQueueItem.objects.filter(pk=job.pk).update(**{field: True})
                job.refresh_from_db()
                self.assertFalse(getattr(job, field))

    def test_duplicate_queue_keys_rejected(self):
        FactoryQueueItem.objects.create(key="discovery:ASTRA-H004")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FactoryQueueItem.objects.create(key="discovery:ASTRA-H004")
