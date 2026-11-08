"""Isolated, no-network customer status copy contract tests."""
import unittest
from datetime import datetime, timedelta, timezone
from services.mpw_purchase_history_copy import buyer_invoice_action


NOW = datetime(2026, 11, 8, 14, 0, tzinfo=timezone.utc)


class PurchaseHistoryCopyTests(unittest.TestCase):
    def test_paid_and_verified_returns_download(self):
        text = buyer_invoice_action(59, "paid", {"status": "paid", "can_download": True}, NOW, NOW)
        self.assertIn('/download/59/', text)

    def test_reviewed_paid_never_grants_download(self):
        text = buyer_invoice_action(59, "paid", {"status": "review", "can_download": False}, NOW, NOW)
        self.assertIn("requires verification", text)
        self.assertNotIn('/download/', text)

    def test_unproven_paid_never_grants_download(self):
        text = buyer_invoice_action(59, "paid", {"status": "awaiting", "can_download": False}, NOW, NOW)
        self.assertIn("requires verification", text)
        self.assertNotIn('/download/', text)

    def test_active_invoice_only_before_expiry(self):
        text = buyer_invoice_action(53, "awaiting_chain", {"status": "awaiting", "can_download": False}, NOW + timedelta(seconds=1), NOW)
        self.assertIn('/invoice/53/', text)

    def test_expiry_boundary_is_not_payable(self):
        text = buyer_invoice_action(54, "awaiting_chain", {"status": "awaiting", "can_download": False}, NOW, NOW)
        self.assertIn("Invoice expired", text)
        self.assertNotIn('/invoice/', text)

    def test_expired_invoice_retains_safe_support_instruction(self):
        text = buyer_invoice_action(55, "awaiting_chain", {"status": "awaiting", "can_download": False}, NOW - timedelta(days=1), NOW)
        self.assertIn("do not pay again", text)
        self.assertIn("transaction hash", text)

    def test_unsupported_state_does_not_offer_invoice(self):
        text = buyer_invoice_action(59, "cancelled", {"status": "awaiting", "can_download": False}, NOW, NOW)
        self.assertIn("not available", text)
        self.assertNotIn('/invoice/', text)

    def test_spoofed_can_download_without_paid_state_is_refused(self):
        text = buyer_invoice_action(59, "awaiting_chain", {"status": "awaiting", "can_download": True}, NOW, NOW)
        self.assertNotIn('/download/', text)

    def test_paid_proof_does_not_override_nonpaid_intent(self):
        text = buyer_invoice_action(59, "awaiting_chain", {"status": "paid", "can_download": True}, NOW, NOW)
        self.assertNotIn('/download/', text)

    def test_malformed_id_and_status_rejected(self):
        for value in (0, -1, "59", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                buyer_invoice_action(value, "paid", {"status": "paid", "can_download": True}, NOW, NOW)
        with self.assertRaises(ValueError):
            buyer_invoice_action(59, "paid", None, NOW, NOW)



class PurchaseHistoryPageTests(unittest.TestCase):
    """Execute the actual purchases() function with in-memory Django stubs."""

    def _render(self, rows, statuses, expiries):
        import ast
        import html
        import sys
        from pathlib import Path
        from types import ModuleType, SimpleNamespace
        from unittest.mock import patch

        class PaymentHold(Exception):
            pass

        class Query:
            def __init__(self, values):
                self.values = values
                self.filters = []

            def select_related(self, *args):
                return self

            def filter(self, **kwargs):
                self.filters.append(kwargs)
                return self

            def order_by(self, *args):
                return self

            def __getitem__(self, key):
                return self.values[key]

        query = Query(rows)
        core_models = ModuleType("core.models")
        core_models.PaymentIntent = SimpleNamespace(objects=query)
        intent_module = ModuleType("services.mpw_walletless_commercial_intent")
        intent_module.PROVIDER = "tron_native"
        decoded = []

        def buyer_status(pk, owner):
            self.assertEqual(owner, 7)
            result = statuses[pk]
            if isinstance(result, Exception):
                raise result
            return result

        def decode(intent):
            decoded.append(intent.pk)
            result = expiries[intent.pk]
            if isinstance(result, Exception):
                raise result
            return SimpleNamespace(expires_at=result)

        intent_module.commercial_buyer_status = buyer_status
        intent_module._decode = decode
        wallet_module = ModuleType("services.mpw_trx_walletless_core")
        wallet_module.PaymentHold = PaymentHold
        django_module = ModuleType("django")
        django_utils = ModuleType("django.utils")
        django_utils.timezone = SimpleNamespace(now=lambda: NOW)
        django_module.utils = django_utils
        source = Path(__file__).resolve().parents[1] / "services/mpw_trx_public_pages.py"
        tree = ast.parse(source.read_text("utf-8"), filename=str(source))
        view = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "purchases")
        view.decorator_list = []
        module = ast.Module(body=[view], type_ignores=[])
        ast.fix_missing_locations(module)
        environment = {
            "_ensure_live": lambda request, **kwargs: None,
            "_page": lambda title, content: content,
            "escape": html.escape,
        }
        with patch.dict(sys.modules, {
            "core.models": core_models,
            "services.mpw_walletless_commercial_intent": intent_module,
            "services.mpw_trx_walletless_core": wallet_module,
            "django": django_module,
            "django.utils": django_utils,
        }):
            exec(compile(module, str(source), "exec"), environment)
            rendered = environment["purchases"](
                SimpleNamespace(user=SimpleNamespace(pk=7))
            )
        self.assertEqual(query.filters, [{
            "provider": "tron_native", "order__customer_id": 7
        }])
        return rendered, decoded

    @staticmethod
    def _row(pk, status, amount="0.03"):
        from types import SimpleNamespace
        return SimpleNamespace(pk=pk, order_id=pk + 100, amount=amount, status=status)

    def test_page_paid_entitlement_skips_duplicate_decode(self):
        body, decoded = self._render(
            [self._row(59, "paid")],
            {59: {"status": "paid", "can_download": True}}, {},
        )
        self.assertIn("/download/59/", body)
        self.assertEqual(decoded, [])

    def test_page_reviewed_paid_has_no_download_or_new_invoice(self):
        body, decoded = self._render(
            [self._row(55, "paid")],
            {55: {"status": "review", "can_download": False}}, {},
        )
        self.assertIn("requires verification", body)
        self.assertNotIn("/download/", body)
        self.assertNotIn("/invoice/", body)
        self.assertEqual(decoded, [])

    def test_page_pending_invoice_is_payable_only_before_expiry(self):
        body, decoded = self._render(
            [self._row(53, "awaiting_chain"), self._row(54, "awaiting_chain")],
            {53: {"status": "awaiting", "can_download": False},
             54: {"status": "awaiting", "can_download": False}},
            {53: NOW + timedelta(seconds=1), 54: NOW},
        )
        self.assertIn("/invoice/53/", body)
        self.assertNotIn("/invoice/54/", body)
        self.assertIn("Invoice expired", body)
        self.assertEqual(decoded, [53, 54])

    def test_page_one_corrupt_invoice_does_not_hide_valid_purchase(self):
        class PaymentHold(Exception):
            pass

        body, decoded = self._render(
            [self._row(53, "awaiting_chain"), self._row(59, "paid")],
            {53: {"status": "awaiting", "can_download": False},
             59: {"status": "paid", "can_download": True}},
            {53: PaymentHold("legacy format")},
        )
        self.assertIn("Order #153", body)
        self.assertIn("manual verification", body)
        self.assertNotIn("/invoice/53/", body)
        self.assertIn("Order #159", body)
        self.assertIn("/download/59/", body)
        self.assertEqual(decoded, [53])

    def test_page_unverifiable_proof_cannot_offer_payment_or_download(self):
        class PaymentHold(Exception):
            pass

        body, decoded = self._render(
            [self._row(54, "paid")],
            {54: PaymentHold("proof unavailable")}, {},
        )
        self.assertIn("manual verification", body)
        self.assertNotIn("/download/", body)
        self.assertNotIn("/invoice/", body)
        self.assertEqual(decoded, [])

    def test_page_other_states_skip_decode_and_escape_amount(self):
        body, decoded = self._render(
            [self._row(55, "cancelled", '<bad>')],
            {55: {"status": "awaiting", "can_download": False}}, {},
        )
        self.assertIn("&lt;bad&gt;", body)
        self.assertNotIn("<bad>", body)
        self.assertNotIn("/invoice/", body)
        self.assertEqual(decoded, [])

if __name__ == "__main__":
    unittest.main()
