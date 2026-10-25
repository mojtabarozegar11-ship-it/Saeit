"""Contract tests: site activity is never mistaken for paid customer demand."""
from copy import deepcopy
from unittest import TestCase

from core.mojplaywin_production_intake import (
    IntakeSourceMismatch,
    build_intake,
    propose_production_orders,
)
from core.mojplaywin_views import FEATURES, SECTIONS, VENTURES


class MojPlayWinProductionIntakeTests(TestCase):
    def test_real_site_cards_are_all_accounted_for(self):
        intake = build_intake(VENTURES, SECTIONS, FEATURES)
        self.assertEqual(intake["proposals_total"], 24)
        self.assertEqual(intake["other_signals_total"], 3 * len(SECTIONS) + len(FEATURES))
        self.assertEqual(intake["mode"], "read_only_proposals")
        self.assertEqual(intake["customer_orders_created"], 0)
        self.assertEqual(intake["factory_tasks_created"], 0)
        self.assertEqual(intake["published_products_created"], 0)
        self.assertEqual(len({p["id"] for p in intake["production_proposals"]}), 24)

    def test_production_candidates_are_never_checkout_items(self):
        for item in propose_production_orders(VENTURES):
            self.assertEqual(item["status"], "proposed_for_review")
            self.assertFalse(item["owner_provenance_verified"])
            self.assertFalse(item["rights_verified"])
            self.assertFalse(item["quality_verified"])
            self.assertFalse(item["customer_demand_verified"])
            self.assertFalse(item["store_publication_allowed"])
            self.assertFalse(item["checkout_enabled"])
            self.assertFalse(item["customer_order"])
            self.assertIsNone(item["price"])
            self.assertEqual(item["source_site"], "mojplaywin.com")
            self.assertTrue(item["source_url"].startswith("/ventures/"))

    def test_deterministic_and_prioritized(self):
        first = propose_production_orders(VENTURES)
        second = propose_production_orders(VENTURES)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["priority_hypothesis"], 5)
        self.assertGreaterEqual(first[0]["priority_hypothesis"], first[-1]["priority_hypothesis"])

    def test_unknown_venture_fails_closed(self):
        modified = deepcopy(VENTURES)
        modified.append({"slug": "unreviewed", "cards": []})
        with self.assertRaises(IntakeSourceMismatch):
            propose_production_orders(modified)

    def test_added_card_fails_closed(self):
        modified = deepcopy(VENTURES)
        modified[0]["cards"].append(("New card", "Unreviewed activity"))
        with self.assertRaises(IntakeSourceMismatch):
            propose_production_orders(modified)

    def test_other_cards_remain_unsold_signals(self):
        signals = build_intake(VENTURES, SECTIONS, FEATURES)["other_activity_signals"]
        self.assertTrue(all(item["status"] == "needs_scoping" and not item["customer_order"] for item in signals))
