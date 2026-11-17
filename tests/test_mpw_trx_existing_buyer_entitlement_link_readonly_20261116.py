"""Paid walletless commerce linkage: never join by coincidental numeric ID."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from scripts.mpw_trx_existing_buyer_entitlement_link_readonly_20261116 import (
    evaluate_links, fk_matches,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/mpw_trx_existing_buyer_entitlement_link_readonly_20261116.py"
WORKFLOW = ROOT / ".github/workflows/mpw-trx-safe-flags-evidence-20261115.yml"


def model(name, relation):
    field = SimpleNamespace(name=name, related_model=(
        SimpleNamespace(_meta=SimpleNamespace(label_lower=relation))
        if relation is not None else None
    ))
    cls = SimpleNamespace(get_field=lambda fieldname: field if name == fieldname else (_ for _ in ()).throw(LookupError("not found")))
    return SimpleNamespace(_meta=cls)


def example(**kwargs):
    values = dict(core_paid=True, commerce_invoice_available=True,
                  commerce_invoice_paid=True, commerce_receipt_available=True,
                  commerce_receipt_same_invoice=True, fulfillment_ready=True,
                  checker_says_allowed=True, checks_are_related=True)
    values.update(kwargs)
    return evaluate_links(**values)


class PaidOrderBuyerEntitlementBoundaryTests(unittest.TestCase):
    def test_exact_core_order_fk_required(self):
        self.assertTrue(fk_matches(model("order", "core.order"), "order", "core.order"))

    def test_same_integer_but_wrong_order_model_refused(self):
        self.assertFalse(fk_matches(model("order", "mpw_commerce.commerceorder"), "order", "core.order"))

    def test_exact_invoice_fk_required(self):
        self.assertTrue(fk_matches(model("invoice", "mpw_commerce.commerceinvoice"),
                                   "invoice", "mpw_commerce.commerceinvoice"))

    def test_unrelated_invoice_relation_refused(self):
        self.assertFalse(fk_matches(model("invoice", "core.paymentintent"),
                                    "invoice", "mpw_commerce.commerceinvoice"))

    def test_exact_order_item_fk_required(self):
        self.assertTrue(fk_matches(model("item", "core.orderitem"), "item", "core.orderitem"))

    def test_unrelated_item_fk_refused(self):
        self.assertFalse(fk_matches(model("item", "mpw_commerce.commerceitem"),
                                    "item", "core.orderitem"))

    def test_missing_relation_refused(self):
        self.assertFalse(fk_matches(model("anything", None), "order", "core.order"))

    def test_none_model_refused(self):
        self.assertFalse(fk_matches(None, "order", "core.order"))

    def test_default_full_chain_still_not_proof_of_customer_download(self):
        state = example()
        self.assertTrue(state["core_paid_receipt_consistent"])
        self.assertFalse(state["file_download_observed"])
        self.assertFalse(state["buyer_acknowledgment_observed"])

    def test_paid_ledger_without_commerce_invoice_flags_bridge_review(self):
        state = example(commerce_invoice_available=False,
                        commerce_invoice_paid=False,
                        commerce_receipt_available=False,
                        commerce_receipt_same_invoice=False)
        self.assertTrue(state["requires_invoice_bridge_review"])
        self.assertFalse(state["requires_receipt_bridge_review"])

    def test_commerce_invoice_but_missing_receipt_requires_review(self):
        state = example(commerce_receipt_available=False,
                        commerce_receipt_same_invoice=False)
        self.assertFalse(state["requires_invoice_bridge_review"])
        self.assertTrue(state["requires_receipt_bridge_review"])

    def test_invalid_fk_does_not_allege_missing_invoice_failure(self):
        state = example(commerce_invoice_available=False,
                        commerce_receipt_available=False, checks_are_related=False)
        self.assertFalse(state["requires_invoice_bridge_review"])
        self.assertFalse(state["requires_receipt_bridge_review"])

    def test_ready_fulfillment_not_sufficient_for_buyer_access(self):
        state = example(checker_says_allowed=False)
        self.assertTrue(state["same_core_item_fulfillment_ready"])
        self.assertTrue(state["entitlement_denied_despite_ready"])
        self.assertFalse(state["file_download_observed"])

    def test_unready_fulfillment_not_falsely_denied_despite_ready(self):
        state = example(fulfillment_ready=False, checker_says_allowed=False)
        self.assertFalse(state["entitlement_denied_despite_ready"])

    def test_paid_false_does_not_trigger_review(self):
        state = example(core_paid=False, commerce_invoice_available=False)
        self.assertFalse(state["requires_invoice_bridge_review"])
        self.assertFalse(state["entitlement_denied_despite_ready"])

    def test_string_boolean_cannot_pass_trust_boundary(self):
        with self.assertRaises(ValueError):
            example(core_paid="true")

    def test_integer_can_not_masquerade_as_boolean(self):
        with self.assertRaises(ValueError):
            example(checker_says_allowed=1)

    def test_no_invoice_or_receipt_or_order_creation_in_source(self):
        s = SOURCE.read_text("utf-8")
        for forbidden in (".save(", ".delete(", "objects.create(",
                          "objects.update(", "objects.delete(",
                          "sendrawtransaction", "broadcasttransaction",
                          "requests.post(", "urllib.request",
                          "private_key", "mnemonic", "seed_phrase",
                          "download_paid_item(", "send_mail("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, s)

    def test_staff_accounts_are_filtered_before_receipt_classification(self):
        s = SOURCE.read_text("utf-8")
        self.assertIn("order.customer.is_staff is True", s)
        self.assertIn('provider=PROVIDER, status="paid"', s)
        self.assertIn("verified_walletless_credit(order, intent) is not True", s)

    def test_same_order_linkage_explicitly_uses_core_fk(self):
        s = SOURCE.read_text("utf-8")
        self.assertIn('fk_matches(invoice_model, "order", "core.order")', s)
        self.assertIn('fk_matches(receipt_model, "invoice", "mpw_commerce.commerceinvoice")', s)
        self.assertIn('fk_matches(fulfillment_model, "item", "core.orderitem")', s)
        self.assertIn('module_item, "_meta"', s)
        self.assertIn('entitlement_core_model', s)

    def test_all_bounds_on_real_customer_records(self):
        s = SOURCE.read_text("utf-8")
        self.assertIn("MAX_PAID = 25", s)
        self.assertIn("MAX_ITEMS = 30", s)
        self.assertIn("qs[:MAX_PAID]", s)
        self.assertIn("[:MAX_ITEMS]", s)

    def test_report_does_not_output_private_order_or_customer(self):
        s = SOURCE.read_text("utf-8")
        for val in ("print(intent)", "print(order)", "print(item)",
                    "print(order.customer)", "print(intent.id)",
                    "print(order.pk)", "print(item.pk)",
                    "print(amount)", "print(txid)"):
            self.assertNotIn(val, s)
        self.assertIn('"read_only": True', s)

    def test_workflow_pins_exact_source_and_only_runs_on_owner_pr(self):
        s = WORKFLOW.read_text("utf-8")
        self.assertIn("scripts/mpw_trx_existing_buyer_entitlement_link_readonly_20261116.py", s)
        self.assertIn("tests.test_mpw_trx_existing_buyer_entitlement_link_readonly_20261116", s)
        self.assertIn("MPW_TRX_EXISTING_BUYER_LINK_READONLY=", s)
        self.assertIn("persist-credentials: false", s)
        self.assertIn("permissions:\n  contents: read", s)
        self.assertNotIn("  push:", s)
        self.assertNotIn("  workflow_dispatch:", s)


if __name__ == "__main__":
    unittest.main()
