"""Offline, noncustomer tests of immutable product/order/payment snapshots."""
from copy import deepcopy
import unittest

from scripts.mojplaywin_product_preservation_snapshot import (
    compare, fingerprint, owner_for, PRODUCT_FIELDS, ORDER_FIELDS, ITEM_FIELDS, PAYMENT_FIELDS,
)


def fixture():
    return {
        "schema": "mojplaywin-preservation-v1",
        "ownership_confirmed_for_every_product": True,
        "row_sha256": {
            "products": {"11": fingerprint({"title": "Example Book", "price": "7.50", "currency": "USD"})},
            "orders": {"91": fingerprint({"status": "pending"})},
            "order_items": {"2": fingerprint({"product_id": 11, "quantity": 1})},
            "payment_intents": {"6": fingerprint({"status": "unpaid"})},
        }
    }


class MojPlayWinPreservationSnapshotTests(unittest.TestCase):
    def test_never_infer_product_domain_from_no_metadata(self):
        self.assertEqual(owner_for({}), "unverified")
        self.assertEqual(owner_for(None), "unverified")
        self.assertEqual(owner_for({"price": "USD", "currency": "ETH"}), "unverified")
        self.assertEqual(owner_for({"site": "MojPlayWin brand"}), "ambiguous")

    def test_exact_host_names_only_and_conflict_detection(self):
        self.assertEqual(owner_for({"domain": "https://mojplaywin.com/"}), "mojplaywin")
        self.assertEqual(owner_for({"site": "www.mojplaywin.com", "domain": "mojplaywin.com"}), "mojplaywin")
        self.assertEqual(owner_for({"domain": "mojplaywin.com.attacker.org"}), "other_explicit_domain")
        self.assertEqual(owner_for({"domain": "zomorodmelal.ir"}), "other_explicit_domain")
        self.assertEqual(owner_for({"domain": "mojplaywin.com", "site": "zomorodmelal.ir"}), "ambiguous")
        self.assertEqual(owner_for({"site": "https://mojplaywin.com/checkout/" }), "ambiguous")

    def test_record_fingerprints_are_stable_but_sensitive_to_changes(self):
        original = {"price": "7.50", "metadata": {"download": "original.pdf", "sku": "A"}}
        reordered = {"metadata": {"sku": "A", "download": "original.pdf"}, "price": "7.50"}
        changed = {"metadata": {"download": "changed.pdf", "sku": "A"}, "price": "7.50"}
        self.assertEqual(fingerprint(original), fingerprint(reordered))
        self.assertNotEqual(fingerprint(original), fingerprint(changed))

    def test_preservation_allows_new_records_but_no_original_change_or_loss(self):
        baseline = fixture()
        after = deepcopy(baseline)
        after["row_sha256"]["orders"]["92"] = fingerprint({"status": "new"})
        self.assertTrue(compare(baseline, after)["accepted"])
        self.assertEqual(compare(baseline, after)["comparisons"]["orders"]["added"], 1)

        for kind in ("products", "orders", "order_items", "payment_intents"):
            with self.subTest(table=kind):
                modified = deepcopy(baseline)
                first = next(iter(modified["row_sha256"][kind]))
                modified["row_sha256"][kind][first] = fingerprint("changed")
                self.assertFalse(compare(baseline, modified)["accepted"])
                missing = deepcopy(baseline)
                missing["row_sha256"][kind].pop(first)
                self.assertFalse(compare(baseline, missing)["accepted"])

    def test_unverified_ownership_blocks_publication(self):
        baseline = fixture()
        after = deepcopy(baseline)
        after["ownership_confirmed_for_every_product"] = False
        self.assertFalse(compare(baseline, after)["accepted"])

    def test_scoped_field_inventory_includes_product_price_and_payment_destination_reference(self):
        for field in ("id", "title", "price", "currency", "active", "owner_id", "metadata"):
            self.assertIn(field, PRODUCT_FIELDS)
        self.assertIn("customer_id", ORDER_FIELDS)
        self.assertIn("product_id", ITEM_FIELDS)
        self.assertIn("provider_reference", PAYMENT_FIELDS)
        self.assertIn("idempotency_key", PAYMENT_FIELDS)


if __name__ == "__main__":
    unittest.main()
