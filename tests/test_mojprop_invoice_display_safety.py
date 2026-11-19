from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from prop_firm.models import PropSimulationIdentity
from prop_firm.simulation_invoice_contract import SimulationInvoiceContract, REQUIRED_GATES
from prop_firm.simulation_invoice_persistence import persist_simulation_invoice
from prop_firm.simulation_checkout_views import _unique_json_pairs
from prop_firm.simulation_identity import is_verified_simulation_user

@override_settings(ALLOWED_HOSTS=["mojplaywin.com"], MPW_SIMULATION_EMAIL_VERIFIER=is_verified_simulation_user,
                   MPW_SIMULATION_RECONCILIATION_ENABLED=True, MPW_SIMULATION_CHECKOUT_ENABLED=True)
class InvoiceDisplaySafetyTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="invoice-safety", email="pay@farmco.org")
        PropSimulationIdentity.objects.create(owner=self.owner, email=self.owner.email, verified_at=timezone.now())
        self.contract = SimulationInvoiceContract("T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb", "a"*64)
        self.invoice = persist_simulation_invoice(order_ref="SIM-DISPLAY", owner=self.owner,
            buyer_email=self.owner.email, contract=self.contract, gates=dict.fromkeys(REQUIRED_GATES, True),
            buyer_terms_acceptance=True)
        self.path = "/moj-prop/invoice/SIM-DISPLAY/"
        self.client.force_login(self.owner)

    def get_invoice(self):
        return self.client.get(self.path, secure=True, HTTP_HOST="mojplaywin.com")

    def test_disabled_runtime_hides_payment_destination_preserves_reconciliation(self):
        with patch("prop_firm.simulation_payment_views.checkout_context", return_value={}):
            response = self.get_invoice()
        self.assertContains(response, "Do not send funds.")
        self.assertNotContains(response, self.contract.recipient)
        self.assertContains(response, "Verify payment")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "pending")

    def test_superseded_contract_hides_payment_destination(self):
        changed = SimulationInvoiceContract(self.contract.recipient, "b"*64)
        with patch("prop_firm.simulation_payment_views.checkout_context", return_value={"simulation_contract":changed}):
            self.assertNotContains(self.get_invoice(), self.contract.recipient)

    def test_matching_contract_can_render_exact_invoice(self):
        with patch("prop_firm.simulation_payment_views.checkout_context", return_value={"simulation_contract":self.contract}):
            self.assertContains(self.get_invoice(), self.contract.recipient)

    def test_duplicate_json_members_refused(self):
        with self.assertRaises(ValueError):
            _unique_json_pairs([("accept_terms", False), ("accept_terms", True)])
