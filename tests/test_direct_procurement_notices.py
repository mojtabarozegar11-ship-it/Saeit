"""Regression tests for the 36+36 undated commercial procurement RFQs."""
import json
import unittest
from pathlib import Path

from core.procurement_notices import get_public_procurement_notices, NOTICE_PATH

ROOT = Path(__file__).resolve().parents[1]


class DirectProcurementNoticesTests(unittest.TestCase):
    def test_exactly_36_product_groups_with_two_distinct_notices(self):
        grouped, _policy = get_public_procurement_notices()
        self.assertEqual(set(grouped), {"supply", "equipment"})
        self.assertEqual(len(grouped["supply"]), 36)
        self.assertEqual(len(grouped["equipment"]), 36)
        for i, (supply, equipment) in enumerate(zip(grouped["supply"], grouped["equipment"]), 1):
            self.assertEqual(supply["id"], f"ZM-SUP-{i:03d}")
            self.assertEqual(equipment["id"], f"ZM-EQP-{i:03d}")
            self.assertEqual(supply["group_code"], i)
            self.assertEqual(equipment["group_code"], i)
            self.assertEqual(supply["group"], equipment["group"])
            self.assertNotEqual(supply["title"], equipment["title"])
            self.assertTrue(supply["scope"])
            self.assertTrue(equipment["scope"])
            self.assertTrue(supply["special_checks"])
            self.assertTrue(equipment["special_checks"])
            self.assertEqual(supply["contact_path"], "/contact/")
            self.assertEqual(equipment["contact_path"], "/contact/")
            self.assertEqual(supply["proposed_public_number"], 349 + i)
            self.assertEqual(equipment["proposed_public_number"], 385 + i)

    def test_no_date_or_deadline_or_binding_purchase(self):
        data = json.loads(NOTICE_PATH.read_text(encoding="utf-8"))
        self.assertTrue(data["policy"]["no_fixed_deadline"])
        self.assertIn("خرید قطعی نیست", data["policy"]["status"])
        self.assertEqual(data["policy"]["channel"], "/contact/")
        self.assertEqual(data["proposed_numbering"]["highest_verified_public_number"], 349)
        self.assertFalse(data["proposed_numbering"]["official_numbers_reserved_in_live_db"])
        forbidden = {"date", "created_at", "published_at", "starts_at", "ends_at", "deadline"}
        for notice in data["notices"]:
            self.assertFalse(forbidden.intersection(notice.keys()))
            self.assertNotIn("price", notice)
            self.assertNotIn("amount", notice)

    def test_public_page_has_both_sections_and_no_private_auction_leak(self):
        view = (ROOT / "core/commerce_views.py").read_text(encoding="utf-8")
        page = (ROOT / "core/templates/core/auctions.html").read_text(encoding="utf-8")
        card = (ROOT / "core/templates/core/includes/procurement_notice_card.html").read_text(encoding="utf-8")
        self.assertIn("get_public_procurement_notices()", view)
        self.assertIn("supply_notices", view)
        self.assertIn("equipment_notices", view)
        self.assertIn("{% for notice in supply_notices %}", page)
        self.assertIn("{% for notice in equipment_notices %}", page)
        self.assertIn("{{ notice.id }}", card)
        self.assertNotIn("PrivateAuction.objects", view)


if __name__ == "__main__":
    unittest.main()
