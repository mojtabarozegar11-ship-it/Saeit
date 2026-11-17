"""Offline invariants for a privacy-safe, single-order TRX buyer audit.

No Django DB, live cPanel session, blockchain call or customer record is used.
"""
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.mpw_existing_paid_buyer_entitlement_readonly_20261116 import (
    exact_one_to_one, product_kind, _base, MAX_PAID, MAX_ITEMS,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mpw_existing_paid_buyer_entitlement_readonly_20261116.py"
WORKFLOW = ROOT / ".github/workflows/mpw-trx-safe-flags-evidence-20261115.yml"


def relation(field="item", label="core.orderitem", one_to_one=True):
    rel = SimpleNamespace(_meta=SimpleNamespace(label_lower=label))
    f = SimpleNamespace(name=field, one_to_one=one_to_one, related_model=rel)
    return SimpleNamespace(_meta=SimpleNamespace(fields=(f,)))


class ExistingBuyerAuditContractTests(unittest.TestCase):
    def test_same_order_item_one_to_one_is_required(self):
        self.assertTrue(exact_one_to_one(relation(), "item", "core.orderitem"))

    def test_invoice_requires_exact_core_order_one_to_one(self):
        self.assertTrue(exact_one_to_one(
            relation("order", "core.order"), "order", "core.order",
        ))

    def test_receipt_requires_exact_invoice_identity(self):
        self.assertTrue(exact_one_to_one(
            relation("invoice", "mpw_commerce.commerceinvoice"),
            "invoice", "mpw_commerce.commerceinvoice",
        ))

    def test_numeric_id_collision_with_other_commerce_order_is_rejected(self):
        self.assertFalse(exact_one_to_one(
            relation("order", "mpw_commerce.order"), "order", "core.order",
        ))

    def test_foreign_item_namespace_cannot_pretend_to_be_same_order_item(self):
        self.assertFalse(exact_one_to_one(
            relation("item", "mpw_commerce.item"), "item", "core.orderitem",
        ))

    def test_many_to_one_relation_is_not_unique_buyer_entitlement(self):
        self.assertFalse(exact_one_to_one(
            relation(one_to_one=False), "item", "core.orderitem",
        ))

    def test_wrong_field_is_rejected(self):
        self.assertFalse(exact_one_to_one(
            relation("order"), "item", "core.orderitem",
        ))

    def test_missing_optional_private_models_fail_closed(self):
        self.assertFalse(exact_one_to_one(None, "item", "core.orderitem"))

    def test_game_cosmetic_is_not_a_downloadable_item(self):
        self.assertEqual(product_kind("game_cosmetic"), "game_cosmetic")
        self.assertNotEqual(product_kind("game_cosmetic"), "explicit_digital")

    def test_only_explicit_known_file_product_types_are_classified_digital(self):
        self.assertEqual(product_kind("digital"), "explicit_digital")
        self.assertEqual(product_kind("digital_book"), "explicit_digital")
        for unknown in ("ebook", "service", "physical", "", None, 27):
            with self.subTest(value=unknown):
                self.assertEqual(product_kind(unknown), "other_or_unknown")

    def test_absent_order_is_never_false_declared_delivered_or_paid(self):
        report = _base()
        self.assertFalse(report["same_order_candidate_found"])
        self.assertIsNone(report["same_order_commerce_invoice_present"])
        self.assertIsNone(report["same_invoice_commerce_receipt_present"])
        self.assertIsNone(report["walletless_same_buyer_download_allowed"])
        self.assertFalse(report["actual_buyer_authenticated_get_performed"])
        self.assertFalse(report["independent_buyer_acknowledged_delivery"])


    def test_guest_outbox_missing_is_not_assumed_for_registered_buyer(self):
        report = _base()
        self.assertIsNone(report["candidate_account_kind"])
        self.assertIsNone(report["guest_outbox_missing_for_guest"])
        s = SCRIPT.read_text("utf-8")
        self.assertIn("from services.mpw_trx_guest_delivery import _guest_user", s)
        self.assertIn('"registered_or_other"', s)
        self.assertIn('result["candidate_account_kind"] == "guest" and outbox is None', s)
        self.assertNotIn('row.order.customer.email', s)

    def test_no_fresh_chain_or_production_write_claim(self):
        report = _base()
        self.assertTrue(report["read_only"])
        self.assertFalse(report["selected_order_fresh_solidity_checked"])
        self.assertFalse(report["production_db_or_files_changed"])

    def test_source_has_hard_bounded_scans(self):
        s = SCRIPT.read_text("utf-8")
        self.assertEqual(MAX_PAID, 25)
        self.assertEqual(MAX_ITEMS, 30)
        self.assertIn("paid[:MAX_PAID]", s)
        self.assertIn("items[:MAX_ITEMS]", s)

    def test_same_order_joins_cannot_use_equal_looking_foreign_ids(self):
        s = SCRIPT.read_text("utf-8")
        self.assertIn('Invoice.objects.filter(order_id=order.pk)', s)
        self.assertIn('Receipt.objects.filter(invoice_id=invoice.pk)', s)
        self.assertIn('Guest.objects.filter(order_id=order.pk)', s)
        self.assertIn('Fulfillment.objects.filter(', s)
        self.assertIn('item_id=item.pk, kind="digital", status="ready"', s)

    def test_paid_refunded_or_staff_accounts_are_excluded_from_candidate(self):
        s = SCRIPT.read_text("utf-8")
        self.assertIn('provider=PROVIDER, status="paid"', s)
        self.assertIn('verified_walletless_credit(order, intent) is not True', s)
        self.assertIn('"refund", "reversal", "chargeback"', s)
        self.assertIn('order.customer.is_staff is True', s)

    def test_both_real_entitlement_paths_checked_but_neither_auto_granted(self):
        s = SCRIPT.read_text("utf-8")
        self.assertIn("can_access_purchased_digital_item", s)
        self.assertIn("commercial_buyer_status", s)
        self.assertIn('value["can_download"]', s)
        self.assertNotIn("grant_entitlement(", s)

    def test_private_asset_only_stat_checked_not_read(self):
        s = SCRIPT.read_text("utf-8")
        self.assertIn("_private_file(item)", s)
        self.assertIn("stat/resolve only", s)
        self.assertNotIn("read_bytes(", s)
        self.assertNotIn("FileResponse(", s)

    def test_no_buyer_ids_transactions_or_financial_writes_printed(self):
        s = SCRIPT.read_text("utf-8")
        for term in (
            "print(intent", "print(order", "print(item", "print(buyer",
            ".save(", ".delete(", "objects.create(", "objects.update(",
            "objects.delete(", "broadcasttransaction", "sendrawtransaction",
            "send_mail(", "EmailMessage(", "urlopen(",
        ):
            with self.subTest(term=term):
                self.assertNotIn(term, s)
        self.assertIn('"read_only": True', s)

    def test_pr_workflow_is_owner_scoped_and_hash_pinned(self):
        s = WORKFLOW.read_text("utf-8")
        self.assertIn("scripts/mpw_existing_paid_buyer_entitlement_readonly_20261116.py", s)
        self.assertIn("tests.test_mpw_existing_paid_buyer_entitlement_readonly_20261116", s)
        self.assertIn("persist-credentials: false", s)
        self.assertIn("pull_request:", s)
        self.assertNotIn("  push:", s)
        self.assertNotIn("  workflow_dispatch:", s)
        self.assertIn("MPW_ONE_PAID_BUYER_ENTITLEMENT_READONLY=", s)
        self.assertIn("git hash-object -- scripts/mpw_existing_paid_buyer_entitlement_readonly_20261116.py", s)


if __name__ == "__main__":
    unittest.main()
