"""Regression tests for the five explicit TRX commercial surfaces."""
from django.test import SimpleTestCase

from core.tron_commerce_surface_registry import (
    CANONICAL_BOT,
    COMMON_BLOCKERS,
    assert_safe_surface_registry,
    build_surface_registry,
    commercial_surface_summary,
    surface_ids,
)


class TronCommerceSurfaceRegistryTests(SimpleTestCase):
    def test_exactly_five_surfaces_use_owner_priority(self):
        rows = build_surface_registry()
        self.assertEqual(len(rows), 5)
        self.assertEqual(
            surface_ids(),
            (
                "moj_prop",
                "signal_sales",
                "zomorod_melal_store",
                "mojplaywin_store",
                "robot_products",
            ),
        )
        self.assertEqual([row["priority"] for row in rows], [1, 2, 3, 4, 5])

    def test_all_routes_use_one_bot_and_native_trx(self):
        rows = build_surface_registry()
        self.assertTrue(all(row["canonical_bot"] == CANONICAL_BOT for row in rows))
        self.assertTrue(all(row["network"] == "TRON" for row in rows))
        self.assertTrue(all(row["asset"] == "TRX" for row in rows))

    def test_every_surface_is_disabled_until_independent_proof(self):
        rows = build_surface_registry()
        self.assertTrue(all(row["status"] == "requested_not_verified" for row in rows))
        self.assertTrue(all(not row["payment_enabled"] for row in rows))
        self.assertTrue(all(not row["checkout_enabled"] for row in rows))
        self.assertTrue(all(not row["invoice_created"] for row in rows))
        self.assertTrue(all(not row["live_gateway_connected"] for row in rows))
        self.assertTrue(all(tuple(row["blockers"]) == COMMON_BLOCKERS for row in rows))

    def test_same_host_does_not_mean_same_merchant_tenant(self):
        rows = build_surface_registry()
        mojplaywin = [row for row in rows if row["host"] == "mojplaywin.com"]
        bot = [row for row in rows if row["host"] == "mojtaba.bot.ai"]
        self.assertEqual({row["surface_id"] for row in mojplaywin}, {"moj_prop", "mojplaywin_store"})
        self.assertEqual({row["surface_id"] for row in bot}, {"signal_sales", "robot_products"})
        self.assertEqual(len({row["tenant_id"] for row in mojplaywin + bot}), 4)

    def test_summary_reports_scope_not_revenue(self):
        summary = commercial_surface_summary()
        self.assertEqual(summary["requested_surface_count"], 5)
        self.assertEqual(summary["live_surface_count"], 0)
        self.assertEqual(summary["invoice_created_count"], 0)
        self.assertFalse(summary["live_gateway_connected"])
        self.assertTrue(summary["independent_tenant_registration_required"])


    def test_registry_accepts_finite_generator_without_mutation(self):
        self.assertTrue(assert_safe_surface_registry(
            item for item in build_surface_registry()
        ))

    def test_registry_bounds_infinite_generator(self):
        def infinite():
            while True:
                yield build_surface_registry()[0]
        with self.assertRaises(ValueError):
            assert_safe_surface_registry(infinite())

    def test_registry_rejects_invalid_collection_types(self):
        for value in (None, "five", b"five", {"surface_id": "moj_prop"}):
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                assert_safe_surface_registry(value)

    def test_registry_rejects_non_mapping_rows(self):
        for bad in (None, object(), [], "moj_prop"):
            with self.subTest(value=type(bad).__name__), self.assertRaises(ValueError):
                rows = list(build_surface_registry())
                rows[0] = bad
                assert_safe_surface_registry(rows)

    def test_registry_rejects_unhashable_id_as_domain_error(self):
        rows = list(build_surface_registry())
        rows[0] = {**rows[0], "surface_id": ["moj_prop"]}
        with self.assertRaises(ValueError):
            assert_safe_surface_registry(rows)

    def test_registry_rejects_boolean_priority_even_if_equal_to_one(self):
        rows = list(build_surface_registry())
        rows[0] = {**rows[0], "priority": True}
        with self.assertRaises(ValueError):
            assert_safe_surface_registry(rows)

    def test_registry_rejects_drifted_source_of_scope(self):
        rows = list(build_surface_registry())
        rows[0] = {**rows[0], "source_of_scope": "owner_override"}
        with self.assertRaises(ValueError):
            assert_safe_surface_registry(rows)

    def test_registry_rejects_malformed_blocker_collection(self):
        for bad in (None, 0, "merchant_entity_verified", {"a": "b"}):
            with self.subTest(value=type(bad).__name__), self.assertRaises(ValueError):
                rows = list(build_surface_registry())
                rows[0] = {**rows[0], "blockers": bad}
                assert_safe_surface_registry(rows)

    def test_registry_rejects_duplicate_or_missing_surface(self):
        rows = list(build_surface_registry())
        with self.assertRaises(ValueError):
            assert_safe_surface_registry(rows[:-1])
        rows[-1] = {**rows[-1], "surface_id": rows[0]["surface_id"]}
        with self.assertRaises(ValueError):
            assert_safe_surface_registry(rows)

    def test_registry_rejects_accidental_activation(self):
        rows = list(build_surface_registry())
        for key in ("payment_enabled", "checkout_enabled", "invoice_created", "live_gateway_connected"):
            with self.subTest(key=key):
                altered = [{**row} for row in rows]
                altered[0][key] = True
                with self.assertRaises(ValueError):
                    assert_safe_surface_registry(altered)

    def test_registry_rejects_wrong_bot_or_host(self):
        rows = list(build_surface_registry())
        for key, value in (("canonical_bot", "other.bot"), ("host", "evil.example")):
            with self.subTest(key=key):
                altered = [{**row} for row in rows]
                altered[0][key] = value
                with self.assertRaises(ValueError):
                    assert_safe_surface_registry(altered)
