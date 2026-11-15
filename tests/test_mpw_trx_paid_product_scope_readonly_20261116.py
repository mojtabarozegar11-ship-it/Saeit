"""Contract tests: cannot confuse game-cosmetic ownership with downloads.

No Django setup, real payments, cPanel, private buyers, RPC or DB writes.
"""
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.mpw_trx_paid_product_scope_readonly_20261116 import (
    category, match_core_relation, evidence_flags, READY_STATUSES,
)

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / "scripts/mpw_trx_paid_product_scope_readonly_20261116.py"
WORKFLOW = ROOT / ".github/workflows/mpw-trx-safe-flags-evidence-20261115.yml"


def fake_model(related=None, name="order"):
    target = (SimpleNamespace(_meta=SimpleNamespace(label_lower=related))
              if related is not None else None)
    field = SimpleNamespace(name=name, related_model=target)
    return SimpleNamespace(_meta=SimpleNamespace(fields=[field]))


def sample(**kwargs):
    defaults = {
        "paid": True, "verified": True, "is_staff": False,
        "has_items": True, "cosmetic": True, "other": False,
        "owned_cosmetic": True, "refund": False,
        "fulfillment": {
            "core_relation_proven": True,
            "same_order_fulfillment_present": True,
            "same_order_ready_record_present": True,
        },
    }
    defaults.update(kwargs)
    return evidence_flags(**defaults)


class ProductAndFulfillmentRiskTests(unittest.TestCase):
    def test_a_game_cosmetic_is_not_a_downloadable_product(self):
        self.assertEqual(category("game_cosmetic"), "game_cosmetic")

    def test_unknown_product_type_is_not_assumed_digital(self):
        self.assertEqual(category("ebook"), "other_product_type")
        self.assertEqual(category("digital"), "other_product_type")

    def test_missing_type_is_not_safely_classifiable(self):
        self.assertEqual(category(None), "unknown")

    def test_nonstring_product_category_is_unknown(self):
        self.assertEqual(category(19), "unknown")

    def test_case_sensitive_category_not_silently_normalized(self):
        self.assertEqual(category("Game_Cosmetic"), "other_product_type")

    def test_core_order_relation_accepted(self):
        self.assertEqual(match_core_relation(fake_model("core.order"), "order"), "core.order")

    def test_foreign_mpw_commerce_order_is_not_core_order(self):
        self.assertIsNone(match_core_relation(fake_model("mpw_commerce.commerceorder"), "order"))

    def test_core_order_item_relation_accepted(self):
        self.assertEqual(match_core_relation(fake_model("core.orderitem", "item"), "item"), "core.orderitem")

    def test_wrong_joined_item_relation_is_rejected(self):
        self.assertIsNone(match_core_relation(fake_model("mpw_commerce.commerceitem", "item"), "item"))

    def test_missing_relation_returns_unknown(self):
        self.assertIsNone(match_core_relation(None, "order"))

    def test_no_automatic_delivery_claim_for_paid_walletless_intent(self):
        flags = sample()
        self.assertTrue(flags["has_valid_stored_walletless_receipt"])
        self.assertFalse(flags["buyer_download_e2e_performed"])
        self.assertFalse(flags["actual_external_buyer_proven"])
        self.assertFalse(flags["fresh_tron_solidity_checked"])

    def test_staff_pilot_is_not_external_customer(self):
        flags = sample(is_staff=True)
        self.assertTrue(flags["staff_or_owner_test_account"])
        self.assertFalse(flags["actual_external_buyer_proven"])

    def test_nonstaff_account_is_not_sufficient_external_proof(self):
        flags = sample(is_staff=False)
        self.assertFalse(flags["staff_or_owner_test_account"])
        self.assertFalse(flags["actual_external_buyer_proven"])

    def test_refund_is_visible_without_false_delivery_claim(self):
        flags = sample(refund=True)
        self.assertTrue(flags["order_has_refund_or_reversal"])
        self.assertFalse(flags["digital_file_delivery_evaluated"])

    def test_unrelated_commerce_fulfillment_cannot_become_same_order(self):
        flags = sample(fulfillment={
            "core_relation_proven": False,
            "same_order_fulfillment_present": False,
            "same_order_ready_record_present": False,
        })
        self.assertFalse(flags["same_order_fulfillment_fk_proven"])
        self.assertFalse(flags["same_order_fulfillment_row_present"])

    def test_no_items_is_not_silently_an_existing_deliverable(self):
        flags = sample(has_items=False)
        self.assertFalse(flags["order_has_items"])

    def test_nonboolean_receipt_proof_rejected(self):
        with self.assertRaises(ValueError):
            sample(verified="true")

    def test_nonboolean_external_user_role_rejected(self):
        with self.assertRaises(ValueError):
            sample(is_staff=0)

    def test_nonboolean_refund_rejected(self):
        with self.assertRaises(ValueError):
            sample(refund="0")

    def test_ready_statuses_do_not_accept_unpaid(self):
        self.assertNotIn("awaiting", READY_STATUSES)
        self.assertNotIn("pending", READY_STATUSES)
        self.assertNotIn("refund", READY_STATUSES)

    def test_source_has_bounded_paid_order_and_item_scan(self):
        s = DIAGNOSTIC.read_text("utf-8")
        self.assertIn("MAX_ORDERS = 25", s)
        self.assertIn("MAX_ITEMS = 30", s)
        self.assertIn("paid[:MAX_ORDERS]", s)
        self.assertIn("items_qs[:MAX_ITEMS]", s)

    def test_source_requires_persisted_walletless_receipt(self):
        s = DIAGNOSTIC.read_text("utf-8")
        self.assertIn("verified_walletless_credit(order, intent) is True", s)
        self.assertIn('provider=PROVIDER, status="paid"', s)
        self.assertIn('order.customer.is_staff is True', s)

    def test_source_game_entitlement_is_not_digital_download(self):
        s = DIAGNOSTIC.read_text("utf-8")
        self.assertIn("from core.crown_fleet import SKUS, owned_skus", s)
        self.assertNotIn("can_access_purchased_digital_item", s)
        self.assertIn('sku_owned = any(', s)

    def test_source_keeps_redacted_financial_state(self):
        s = DIAGNOSTIC.read_text("utf-8")
        for value in ("print(intent)", "print(order)", "print(item)",
                      "print(order.customer)", "print(ADDRESS)",
                      ".save(", ".delete(", "objects.create(",
                      "objects.update(", "objects.delete(",
                      "broadcasttransaction", "sendrawtransaction",
                      "requests.post(", "urlopen(",
                      "private_key", "seed_phrase", "mnemonic"):
            with self.subTest(forbidden=value):
                self.assertNotIn(value, s)
        self.assertIn('"fresh_solidity_confirmation_performed": False', s)

    def test_failed_db_cannot_be_reported_as_zero_sales(self):
        s = DIAGNOSTIC.read_text("utf-8")
        self.assertIn('"db_inspection_available": False', s)
        self.assertIn('"paid_order_review_exhaustive": False', s)
        self.assertIn('type(exc).__name__', s)

    def test_privileged_readonly_workflow_has_no_push_or_dispatch(self):
        s = WORKFLOW.read_text("utf-8")
        self.assertIn("scripts/mpw_trx_paid_product_scope_readonly_20261116.py", s)
        self.assertIn("tests.test_mpw_trx_paid_product_scope_readonly_20261116", s)
        self.assertIn("permissions:\n  contents: read", s)
        self.assertIn("persist-credentials: false", s)
        self.assertIn("pull_request:", s)
        self.assertNotIn("  push:", s)
        self.assertNotIn("  workflow_dispatch:", s)

    def test_report_contract_does_not_leak_secrets_or_ids(self):
        s = WORKFLOW.read_text("utf-8")
        self.assertIn("MPW_TRX_PAID_PRODUCT_SCOPE_READONLY=", s)
        self.assertIn('"mpw.trx.existing.paid.product.delivery.v1"', s)
        self.assertNotIn("curl -X POST", s)
        self.assertNotIn("manage.py migrate", s)


if __name__ == "__main__":
    unittest.main()
