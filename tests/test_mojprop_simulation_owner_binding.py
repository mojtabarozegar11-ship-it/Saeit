from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from prop_firm.models import (
    PropPlan1Invoice, PropPlan1Receipt, PropSimulationAccount,
    PropSimulationInvoiceOwner, PropRewardReserveAllocation,
)
from prop_firm.simulation_invoice_contract import SimulationInvoiceContract, REQUIRED_GATES
from prop_firm.simulation_invoice_persistence import persist_simulation_invoice
from prop_firm.simulation_settlement import settle_and_provision

class SimulationOwnerBindingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="sim-one", email="sim@farmco.org")
        self.other = User.objects.create_user(username="sim-two", email="sim@farmco.org")
        self.contract = SimulationInvoiceContract("T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb", "a"*64)
        self.gates = dict.fromkeys(REQUIRED_GATES, True)

    def issue(self, owner=None, ref="SIM-012"):
        owner = owner or self.owner
        return persist_simulation_invoice(order_ref=ref, owner=owner, buyer_email=owner.email,
            contract=self.contract, gates=self.gates, buyer_terms_acceptance=True)

    def settle(self, invoice, owner=None, **overrides):
        owner = owner or self.owner
        params = dict(invoice_id=invoice.pk, owner=owner, tx_hash="b"*64,
            observed_network="tron-mainnet", observed_asset="TRX",
            observed_recipient=invoice.recipient, observed_amount_sun=invoice.amount_sun,
            independently_finalized=True, evidence_digest="c"*64,
            verified_owner_email=owner.email)
        return settle_and_provision(**(params | overrides))

    def test_owner_binding_and_issue_idempotency(self):
        invoice = self.issue()
        self.assertEqual(self.issue().pk, invoice.pk)
        self.assertEqual(PropSimulationInvoiceOwner.objects.get(invoice=invoice).owner_id, self.owner.pk)
        with self.assertRaises(ValidationError):
            self.issue(self.other)
        self.assertEqual(PropPlan1Invoice.objects.count(), 1)

    def test_same_email_does_not_confer_invoice_ownership(self):
        invoice = self.issue()
        with self.assertRaises(ValidationError):
            self.settle(invoice, self.other)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "pending")
        self.assertFalse(PropSimulationAccount.objects.exists())

    def test_wrong_amount_cannot_issue_receipt_or_account(self):
        invoice = self.issue()
        with self.assertRaises(ValidationError):
            self.settle(invoice, observed_amount_sun=29_000_000)
        self.assertFalse(PropPlan1Receipt.objects.exists())
        self.assertFalse(PropSimulationAccount.objects.exists())

    def test_success_creates_exactly_one_receipt_reserve_and_account(self):
        invoice = self.issue()
        receipt, account = self.settle(invoice)
        receipt2, account2 = self.settle(invoice)
        self.assertEqual(receipt.pk, receipt2.pk)
        self.assertEqual(account.pk, account2.pk)
        self.assertEqual(account.owner_id, self.owner.pk)
        self.assertEqual(account.starting_balance_usd, 1000)
        self.assertEqual(account.challenge_days, 60)
        self.assertEqual(PropRewardReserveAllocation.objects.count(), 1)
        self.assertEqual(PropPlan1Receipt.objects.count(), 1)
        self.assertEqual(PropSimulationAccount.objects.count(), 1)

    def test_same_transaction_cannot_settle_two_invoices(self):
        first = self.issue()
        second = self.issue(ref="SIM-013")
        self.settle(first)
        with self.assertRaises(ValidationError):
            self.settle(second)
        second.refresh_from_db()
        self.assertEqual(second.status, "pending")
        self.assertEqual(PropSimulationAccount.objects.count(), 1)


    def test_commercial_v3_settlement_preserves_version_and_reserve(self):
        from prop_firm.simulation_invoice_contract import COMMERCIAL_CONTRACT_VERSION
        from prop_firm.simulation_fulfillment import verified_simulation_purchase
        self.contract = SimulationInvoiceContract(
            "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb", "a"*64,
            version=COMMERCIAL_CONTRACT_VERSION)
        invoice = self.issue()
        receipt, account = self.settle(invoice)
        self.assertEqual(invoice.contract_version, COMMERCIAL_CONTRACT_VERSION)
        self.assertEqual(account.owner_id, self.owner.pk)
        result = verified_simulation_purchase(invoice_id=invoice.pk, buyer_email=self.owner.email)
        self.assertEqual(result["data_mode"], "licensed_market_data")
        allocation = PropRewardReserveAllocation.objects.get(invoice=invoice)
        self.assertEqual(allocation.reward_reserve_sun, 24_000_000)
        self.assertEqual(allocation.refund_reserve_sun, 3_000_000)
        self.assertEqual(allocation.operating_buffer_sun, 3_000_000)
