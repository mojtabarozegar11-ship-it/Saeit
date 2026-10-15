"""Django-isolated Astra 0049 evidence queue: no commercial bypass paths."""
import hashlib

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from core.models import FactoryQueueItem, DiscoverySnapshot


class AstraStage45EvidenceSchemaTests(TestCase):
    def sample(self, key="discovery:field-needs-1"):
        return FactoryQueueItem.objects.create(
            key=key,
            kind="discovery",
            record={"hypothesis": "private synthetic demonstration, not buyer proof"},
        )

    def test_default_research_only_blocks_commerce(self):
        q=self.sample()
        self.assertEqual(q.stage,"HYPOTHESIS")
        self.assertFalse(q.market_demand_verified)
        self.assertFalse(q.publication_allowed)
        self.assertIsNone(q.commercial_quality_score)
        self.assertEqual(q.discovery_snapshots.count(),0)

    def test_provisional_source_snapshot_does_not_assert_market(self):
        q=self.sample()
        row=DiscoverySnapshot.objects.create(
            hypothesis=q,
            url="https://example.org/educational",
            content_hash=hashlib.sha256(b"fictional").hexdigest(),
            retrieved_at=timezone.now(),
            record={"claim_type":"problem",
                    "note":"illustrative, not independently verified"},
        )
        self.assertFalse(row.independently_verified)
        self.assertEqual(q.discovery_snapshots.first().pk,row.pk)
        self.assertFalse(q.market_demand_verified)

    def test_duplicate_snapshot_is_rejected_by_database(self):
        q=self.sample()
        data=dict(hypothesis=q,url="https://example.org/one",
                  content_hash="0"*64,retrieved_at=timezone.now(),
                  record={"claim_type":"problem"})
        DiscoverySnapshot.objects.create(**data)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DiscoverySnapshot.objects.create(**data)

    def test_publication_true_blocked_at_db_level(self):
        q=self.sample()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FactoryQueueItem.objects.filter(pk=q.pk).update(publication_allowed=True)
        self.assertFalse(FactoryQueueItem.objects.get(pk=q.pk).publication_allowed)

    def test_demand_verified_true_blocked_at_db_level(self):
        q=self.sample()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FactoryQueueItem.objects.filter(pk=q.pk).update(market_demand_verified=True)

    def test_fabricated_commercial_score_blocked(self):
        q=self.sample()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FactoryQueueItem.objects.filter(pk=q.pk).update(commercial_quality_score=100)

    def test_snapshot_self_verified_true_blocked(self):
        q=self.sample()
        row=DiscoverySnapshot.objects.create(
            hypothesis=q,url="https://example.edu/test",
            content_hash="a"*64,retrieved_at=timezone.now())
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DiscoverySnapshot.objects.filter(pk=row.pk).update(independently_verified=True)

    def test_snapshot_blocks_deleting_its_parent(self):
        q=self.sample()
        DiscoverySnapshot.objects.create(
            hypothesis=q,url="https://example.edu/research",
            content_hash="b"*64,retrieved_at=timezone.now())
        with self.assertRaises(ProtectedError):
            q.delete()

    def test_invalid_commercial_stage_not_an_authorized_choice(self):
        q=self.sample()
        q.stage="QUALIFIED_FOR_SALE"
        with self.assertRaises(ValidationError):
            q.full_clean()

    def test_existing_readonly_bridge_schema_is_supported(self):
        with connection.cursor() as cur:
            for table, required in (
                ("core_factoryqueueitem", {"id","key","kind"}),
                ("core_discoverysnapshot",
                 {"id","hypothesis_id","url","content_hash","retrieved_at","record"}),
            ):
                columns={c.name for c in connection.introspection.get_table_description(cur,table)}
                self.assertTrue(required.issubset(columns))
