"""Pure tests: existing CRM queue diagnostic must not emit customer records."""
import json
import unittest

from scripts.mojprop_live_sales_queue_boolean_readonly_20261116 import (
    CATEGORIES, git_blob_sha256_legacy_sha1, sanitize_action_queue,
    inspect_minimal_intake_presence,
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


class MinimalIntakeFallbackTests(unittest.TestCase):
    def simulate(self, *results):
        class Cursor:
            def __init__(self):
                self.queries = []
                self.answers = iter(results)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, query):
                if not query.lstrip().upper().startswith("SELECT "):
                    raise AssertionError("mutation attempted")
                self.queries.append(query)
            def fetchone(self):
                return (next(self.answers),)
        class DB:
            def __init__(self):
                self.cursor_instance = Cursor()
            def cursor(self):
                return self.cursor_instance
        db = DB()
        out = inspect_minimal_intake_presence(db)
        self.assertTrue(all("SELECT" in q for q in db.cursor_instance.queries))
        self.assertFalse(out["exact_lead_counts_or_personal_data_emitted"])
        self.assertFalse(out["offer_or_payment_created"])
        return out, len(db.cursor_instance.queries)

    def test_missing_live_table_is_unknown_not_zero_leads(self):
        out, queries = self.simulate(0)
        self.assertIsNone(out["any_actionable_consent_scoped_lead"])
        self.assertFalse(out["limited_intake_presence_checked"])
        self.assertEqual(queries, 1)

    def test_missing_consent_column_is_unknown_not_zero_leads(self):
        out, queries = self.simulate(1, 1)
        self.assertIsNone(out["any_actionable_consent_scoped_lead"])
        self.assertFalse(out["limited_intake_presence_checked"])
        self.assertEqual(queries, 2)

    def test_live_consented_inquiry_exists_without_revealing_identity(self):
        out, queries = self.simulate(1, 2, 1)
        self.assertTrue(out["any_actionable_consent_scoped_lead"])
        self.assertEqual(out["categories_with_work_pending"], ["consented_active_intake"])
        self.assertEqual(queries, 3)
        self.assertNotIn("private@example", json.dumps(out))

    def test_verified_empty_table_is_false_but_no_revenue_claim(self):
        out, queries = self.simulate(1, 2, 0)
        self.assertFalse(out["any_actionable_consent_scoped_lead"])
        self.assertEqual(out["categories_with_work_pending"], [])
        self.assertTrue(out["limited_intake_presence_checked"])
        self.assertFalse(out["revenue_recognized"])
        self.assertEqual(queries, 3)


if __name__ == "__main__":
    unittest.main()
