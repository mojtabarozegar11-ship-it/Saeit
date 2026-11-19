"""Retry admission using signed replay evidence and existing unique invoice key."""
import uuid
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from prop_firm.models import PropSimulationIdentity, PropPlan1Invoice
from prop_firm.simulation_invoice_contract import SimulationInvoiceContract, REQUIRED_GATES, COMMERCIAL_CONTRACT_VERSION
from prop_firm.simulation_invoice_persistence import persist_simulation_invoice
from prop_firm.simulation_settlement import settle_and_provision
from prop_firm.simulation_retry import retry_reference
from prop_firm.simulation_event_service import _append_event, ROOT, VERSION

@override_settings(MPW_SIMULATION_EVENT_KEY="ci-only-"+"a"*48)
class SimulationRetryTests(TestCase):
    def setUp(self):
        self.owner=get_user_model().objects.create_user(username="retry-owner",email="retry@example.org")
        PropSimulationIdentity.objects.create(owner=self.owner,email=self.owner.email,verified_at=timezone.now())
        self.gates=dict.fromkeys(REQUIRED_GATES, True)
        self.first=SimulationInvoiceContract("T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb","a"*64,version=COMMERCIAL_CONTRACT_VERSION)
        self.retry=SimulationInvoiceContract(self.first.recipient,self.first.terms_digest,"retry",COMMERCIAL_CONTRACT_VERSION)
        invoice=persist_simulation_invoice(order_ref="SIM-RETRY-SOURCE", owner=self.owner,buyer_email=self.owner.email,contract=self.first,gates=self.gates,buyer_terms_acceptance=True)
        _,self.account=settle_and_provision(invoice_id=invoice.pk,owner=self.owner,tx_hash="b"*64,observed_network="tron-mainnet",observed_asset="TRX",observed_recipient=invoice.recipient,observed_amount_sun=invoice.amount_sun,independently_finalized=True,evidence_digest="c"*64,verified_owner_email=self.owner.email)
    def fail_challenge(self):
        payload={"version":VERSION,"operation":"submit","order":{"order_id":"gap","symbol":"EURUSD","side":"buy","quantity":"10","order_type":"market","limit_price":None,"stop_price":None,"stop_loss":"99","take_profit":None},"quote":{"symbol":"EURUSD","bid":"100","ask":"101","timestamp":"2026-11-19T00:00:01Z","sequence":1}}
        _append_event(self.account,1,uuid.uuid4(),ROOT,payload)
        _append_event(self.account,2,uuid.uuid4(),self.account.event_head_digest,{"version":VERSION,"operation":"quote","quote":{"symbol":"EURUSD","bid":"90","ask":"91","timestamp":"2026-11-19T00:00:02Z","sequence":2}})
    def issue(self, **changes):
        args=dict(order_ref=retry_reference(self.account),owner=self.owner,buyer_email=self.owner.email,contract=self.retry,gates=self.gates,buyer_terms_acceptance=True,retry_account_id=self.account.pk)
        return persist_simulation_invoice(**{**args,**changes})
    def test_caller_boolean_does_not_grant_retry(self):
        with self.assertRaises(ValidationError):self.issue(retry_eligibility_verified=True,retry_account_id=None)
    def test_active_unfailed_denied(self):
        with self.assertRaises(ValidationError):self.issue()
    def test_expired_review_alone_denied(self):
        self.account.status="expired_review"
        self.account.save(update_fields=["status"])
        with self.assertRaises(ValidationError):self.issue()
    def test_verified_failure_issues_one_18_trx_invoice(self):
        self.fail_challenge()
        a=self.issue()
        b=self.issue()
        self.assertEqual(a.pk,b.pk)
        self.assertEqual(a.amount_sun,18_000_000)
        self.assertEqual(PropPlan1Invoice.objects.count(),2)
    def test_arbitrary_retry_ref_denied(self):
        self.fail_challenge()
        with self.assertRaises(ValidationError):self.issue(order_ref="SIM-OTHER")
    def test_first_cannot_use_retry_namespace(self):
        with self.assertRaises(ValidationError):self.issue(contract=self.first,retry_account_id=None)
    def test_other_owner_denied(self):
        self.fail_challenge()
        other=get_user_model().objects.create_user(username="retry-other",email="other@example.org")
        PropSimulationIdentity.objects.create(owner=other,email=other.email,verified_at=timezone.now())
        with self.assertRaises(ValidationError):self.issue(owner=other,buyer_email=other.email)
