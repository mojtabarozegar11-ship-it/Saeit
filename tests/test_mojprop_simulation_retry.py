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

    def test_retry_page_and_post_bind_same_account_and_reuse_invoice(self):
        from unittest.mock import patch
        from django.urls import reverse
        from prop_firm.simulation_checkout_views import SALT
        from django.core import signing
        self.fail_challenge()
        self.client.force_login(self.owner)
        ctx={"simulation_checkout_ready":True,"simulation_terms":"Reviewed simulation terms",
             "simulation_terms_digest":self.first.terms_digest,
             "simulation_contract":self.first,"simulation_gates":self.gates}
        with override_settings(ALLOWED_HOSTS=["mojplaywin.com"],MPW_SIMULATION_IDENTITY_ENABLED=True), \
                patch("prop_firm.simulation_checkout_views.checkout_context",return_value=ctx), \
                patch("prop_firm.simulation_dashboard_views.checkout_context",return_value=ctx):
            page=self.client.get(reverse("moj_prop_dashboard"),{"retry":self.account.pk},secure=True,HTTP_HOST="mojplaywin.com")
            self.assertContains(page,"18 TRX retry invoice")
            token=page.context["retry_checkout"]["checkout_token"]
            parsed=signing.loads(token,salt=SALT)
            self.assertEqual(parsed["retry_account_id"],self.account.pk)
            self.assertEqual(parsed["contract"],self.retry.digest())
            self.assertEqual(PropPlan1Invoice.objects.count(),1)
            data={"accept_terms":"yes","terms_digest":self.first.terms_digest,"checkout_token":token}
            url=reverse("moj_prop_simulation_checkout")
            self.assertEqual(self.client.post(url,data,secure=True,HTTP_HOST="mojplaywin.com").status_code,302)
            self.assertEqual(self.client.post(url,data,secure=True,HTTP_HOST="mojplaywin.com").status_code,302)
            self.assertEqual(PropPlan1Invoice.objects.count(),2)
            self.assertEqual(PropPlan1Invoice.objects.get(order_ref=parsed["order_ref"]).amount_sun,18_000_000)
            parsed["retry_account_id"]+=100000
            data["checkout_token"]=signing.dumps(parsed,salt=SALT)
            self.assertEqual(self.client.post(url,data,secure=True,HTTP_HOST="mojplaywin.com").status_code,400)

    def test_retry_page_gate_closed(self):
        from django.urls import reverse
        self.client.force_login(self.owner)
        with override_settings(ALLOWED_HOSTS=["mojplaywin.com"],MPW_SIMULATION_IDENTITY_ENABLED=True,MPW_SIMULATION_CHECKOUT_ENABLED=False):
            page=self.client.get(reverse("moj_prop_dashboard"),{"retry":self.account.pk},secure=True,HTTP_HOST="mojplaywin.com")
            self.assertNotContains(page,"Create or reopen my 18 TRX retry invoice")
            self.assertEqual(PropPlan1Invoice.objects.count(),1)

    def test_retry_payment_page_exact_amount_and_fail_closed_on_drift(self):
        from unittest.mock import patch
        from django.urls import reverse
        from dataclasses import replace
        self.fail_challenge()
        invoice=self.issue()
        self.client.force_login(self.owner)
        url=reverse("moj_prop_simulation_invoice",kwargs={"order_ref":invoice.order_ref})
        ctx={"simulation_contract":self.first}
        with override_settings(ALLOWED_HOSTS=["mojplaywin.com"],MPW_SIMULATION_RECONCILIATION_ENABLED=True,
                MPW_SIMULATION_EMAIL_VERIFIER=lambda user: user.is_authenticated):
            with patch("prop_firm.simulation_payment_views.checkout_context",return_value=ctx):
                response=self.client.get(url,secure=True,HTTP_HOST="mojplaywin.com")
                self.assertContains(response,"Amount: 18 TRX (18000000 SUN)")
                self.assertNotContains(response,"Amount: 30 TRX")
                self.assertContains(response,invoice.order_ref)
                self.assertTrue(response.context["show_payment_instructions"])
            with patch("prop_firm.simulation_payment_views.checkout_context",
                       return_value={"simulation_contract":replace(self.first,terms_digest="d"*64)}):
                response=self.client.get(url,secure=True,HTTP_HOST="mojplaywin.com")
                self.assertFalse(response.context["show_payment_instructions"])
                self.assertContains(response,"Do not send funds")
            with patch("prop_firm.simulation_payment_views.checkout_context",return_value={}):
                response=self.client.get(url,secure=True,HTTP_HOST="mojplaywin.com")
                self.assertFalse(response.context["show_payment_instructions"])
            self.client.force_login(get_user_model().objects.create_user(username="retry-unowned",email=self.owner.email))
            self.assertEqual(self.client.get(url,secure=True,HTTP_HOST="mojplaywin.com").status_code,404)

    def test_retry_settlement_creates_one_account_and_exact_reserve(self):
        from prop_firm.models import PropRewardReserveAllocation, PropSimulationAccount
        self.fail_challenge()
        invoice=self.issue()
        params=dict(invoice_id=invoice.pk,owner=self.owner,tx_hash="d"*64,
            observed_network="tron-mainnet",observed_asset="TRX",observed_recipient=invoice.recipient,
            observed_amount_sun=18_000_000,independently_finalized=True,evidence_digest="e"*64,
            verified_owner_email=self.owner.email)
        with self.assertRaises(ValidationError):
            settle_and_provision(**{**params,"observed_amount_sun":30_000_000})
        receipt,account=settle_and_provision(**params)
        receipt2,account2=settle_and_provision(**params)
        self.assertEqual((receipt.pk,account.pk),(receipt2.pk,account2.pk))
        self.assertEqual(PropSimulationAccount.objects.count(),2)
        allocation=PropRewardReserveAllocation.objects.get(invoice=invoice)
        self.assertEqual((allocation.reward_reserve_sun,allocation.refund_reserve_sun,
                          allocation.operating_buffer_sun),(14_400_000,1_800_000,1_800_000))
