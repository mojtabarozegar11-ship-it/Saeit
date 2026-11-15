"""Pure tests: existing CRM queue diagnostic must not emit customer records."""
import json
import unittest

from scripts.mojprop_live_sales_queue_boolean_readonly_20261116 import (
    CATEGORIES, git_blob_sha256_legacy_sha1, sanitize_action_queue,
)


def fixture():
    return {
        "schema": "mojprop.sales_action_queue.v1",
        "categories": [
            {"category": name, "count": int(name == "urgent_unreviewed"),
             "request_refs": ["PRIVATE-IDENTIFIER-NOT-FOR-LOGS"],
             "customer_email": "private@example.test",
             "notes": "private customer trading circumstances"}
            for name in sorted(CATEGORIES)
        ],
    }


class LiveMojPropQueuePrivacyTests(unittest.TestCase):
    def test_git_blob_algorithm_matches_git_empty_blob(self):
        self.assertEqual(git_blob_sha256_legacy_sha1(b""),
                         "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")

    def test_only_aggregate_boolean_categories_leave_host(self):
        result = sanitize_action_queue(fixture())
        raw = json.dumps(result, sort_keys=True)
        self.assertTrue(result["any_actionable_consent_scoped_lead"])
        self.assertEqual(result["categories_with_work_pending"], ["urgent_unreviewed"])
        self.assertNotIn("private@example", raw)
        self.assertNotIn("PRIVATE-IDENTIFIER", raw)
        self.assertNotIn("customer", raw.lower().replace("customer_contact_sent", ""))
        self.assertIs(result["offer_or_payment_created"], False)
        self.assertIs(result["customer_contact_sent"], False)

    def test_all_categories_empty_is_not_a_fabricated_sale(self):
        data = fixture()
        for item in data["categories"]:
            item["count"] = 0
        result = sanitize_action_queue(data)
        self.assertFalse(result["any_actionable_consent_scoped_lead"])
        self.assertEqual(result["categories_with_work_pending"], [])
        self.assertFalse(result["revenue_recognized"])

    def test_absent_duplicate_or_unknown_category_is_not_reported(self):
        data = fixture()
        with self.assertRaises(ValueError):
            sanitize_action_queue({**data, "categories": data["categories"][:-1]})
        new = fixture()
        new["categories"][1]["category"] = new["categories"][0]["category"]
        with self.assertRaises(ValueError):
            sanitize_action_queue(new)
        new = fixture()
        new["categories"][0]["category"] = "all_customer_email_addresses"
        with self.assertRaises(ValueError):
            sanitize_action_queue(new)

    def test_untrusted_counts_cannot_be_truthy_or_excessive(self):
        for value in (True, "10", 0.1, -1, 1_000_001, None):
            with self.subTest(value=value):
                data = fixture()
                data["categories"][0]["count"] = value
                with self.assertRaises(ValueError):
                    sanitize_action_queue(data)

    def test_bad_schema_never_serializes_a_raw_private_report(self):
        for report in (None, [], {}, {"schema": "unexpected", "categories": []}):
            with self.subTest(report=report):
                with self.assertRaises(ValueError):
                    sanitize_action_queue(report)


if __name__ == "__main__":
    unittest.main()
