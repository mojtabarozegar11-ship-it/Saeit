"""Protect the commerce funnel and Moj Prop migration DAG against forked heads."""
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase


class CoreRevenueMigrationGraphTests(SimpleTestCase):
    def test_core_migrations_have_one_leaf(self):
        loader = MigrationLoader(None)
        core_leaves = [node for node in loader.graph.leaf_nodes() if node[0] == "core"]
        self.assertEqual(
            core_leaves, [("core", "0043_alter_mojproprequest_source")]
        )

    def test_merge_preserves_both_independent_schema_ancestries(self):
        loader = MigrationLoader(None)
        merge = ("core", "0042_merge_commercefunnel_mojprop")
        plan = loader.graph.forwards_plan(merge)
        self.assertIn(("core", "0040_commercefunnelevent"), plan)
        self.assertIn(("core", "0041_mojprop_request"), plan)
        self.assertLess(plan.index(("core", "0040_commercefunnelevent")), plan.index(merge))
        self.assertLess(plan.index(("core", "0041_mojprop_request")), plan.index(merge))

    def test_source_schema_alignment_follows_non_destructive_merge(self):
        loader = MigrationLoader(None)
        adjustment = loader.disk_migrations[
            ("core", "0043_alter_mojproprequest_source")
        ]
        self.assertEqual(
            adjustment.dependencies, [("core", "0042_merge_commercefunnel_mojprop")]
        )
        self.assertEqual(len(adjustment.operations), 1)
        self.assertEqual(adjustment.operations[0].model_name, "mojproprequest")
        self.assertEqual(adjustment.operations[0].name, "source")
        self.assertTrue(adjustment.operations[0].field.blank)

    def test_merge_does_not_rewrite_or_drop_production_tables(self):
        loader = MigrationLoader(None)
        merge = loader.disk_migrations[
            ("core", "0042_merge_commercefunnel_mojprop")
        ]
        self.assertEqual(merge.operations, [])
        self.assertEqual(
            set(merge.dependencies),
            {
                ("core", "0040_commercefunnelevent"),
                ("core", "0041_mojprop_request"),
            },
        )
