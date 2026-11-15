"""P0 migration-leaf repair without making or rewriting production data."""
from django.test import SimpleTestCase
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.models import CreateModel

LEFT = ("core", "0040_commercefunnelevent")
RIGHT = ("core", "0041_mojprop_request")
MERGE = ("core", "0042_merge_commerce_funnel_mojprop_20261115")
BASE = ("core", "0039_educationassessment_educationattempt_and_more")


class CoreCommercialMigrationMergeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.loader = MigrationLoader(None)

    def test_core_has_exactly_one_leaf(self):
        self.assertEqual(self.loader.graph.leaf_nodes("core"), [MERGE])

    def test_no_core_migration_conflict_remains(self):
        self.assertNotIn("core", self.loader.detect_conflicts())

    def test_merge_depends_on_both_independent_business_models(self):
        self.assertEqual(set(self.loader.disk_migrations[MERGE].dependencies),
                         {LEFT, RIGHT})

    def test_merge_migration_never_alters_existing_business_tables(self):
        self.assertEqual(self.loader.disk_migrations[MERGE].operations, [])

    def test_commerce_funnel_branch_comes_directly_from_common_parent(self):
        self.assertIn(BASE, self.loader.disk_migrations[LEFT].dependencies)

    def test_moj_prop_request_branch_comes_directly_from_common_parent(self):
        self.assertIn(BASE, self.loader.disk_migrations[RIGHT].dependencies)

    def test_commerce_branch_creates_only_funnel_model(self):
        created = [op.name for op in self.loader.disk_migrations[LEFT].operations
                   if isinstance(op, CreateModel)]
        self.assertEqual(created, ["CommerceFunnelEvent"])

    def test_moj_prop_branch_creates_only_interest_request_model(self):
        created = [op.name for op in self.loader.disk_migrations[RIGHT].operations
                   if isinstance(op, CreateModel)]
        self.assertEqual(created, ["MojPropRequest"])

    def test_both_branches_are_in_merge_execution_plan(self):
        plan = self.loader.graph.forwards_plan(MERGE)
        self.assertIn(LEFT, plan)
        self.assertIn(RIGHT, plan)
        self.assertEqual(plan[-1], MERGE)
