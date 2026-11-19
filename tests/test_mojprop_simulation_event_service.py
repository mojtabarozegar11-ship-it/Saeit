import uuid
from decimal import Decimal as D
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from prop_firm.models import PropSimulationIdentity, PropSimulationEvent
from prop_firm.simulation_invoice_contract import SimulationInvoiceContract, REQUIRED_GATES
from prop_firm.simulation_invoice_persistence import persist_simulation_invoice
from prop_firm.simulation_settlement import settle_and_provision
from prop_firm.simulation_engine import MarketQuote, OrderRequest
from prop_firm.simulation_event_service import record_command, account_snapshot, advance_account_quotes

def quote_provider(*, account_id, symbol):
    return MarketQuote(symbol, D("100"), D("101"), "2026-11-19T00:00:01Z", 1)

@override_settings(MPW_SIMULATION_TRADING_ENABLED=True,
    MPW_SIMULATION_EVENT_KEY="ci-only-"+"a"*48, MPW_SIMULATION_QUOTE_PROVIDER=quote_provider)
class SimulationEventTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="event-buyer", email="event@farmco.org")
        PropSimulationIdentity.objects.create(owner=self.owner, email=self.owner.email, verified_at=timezone.now())
        invoice = persist_simulation_invoice(order_ref="SIM-LEDGER-TEST", owner=self.owner,
            buyer_email=self.owner.email, contract=SimulationInvoiceContract(
                "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb", "a"*64),
            gates=dict.fromkeys(REQUIRED_GATES, True), buyer_terms_acceptance=True)
        _, self.account = settle_and_provision(invoice_id=invoice.pk, owner=self.owner,
            tx_hash="b"*64, observed_network="tron-mainnet", observed_asset="TRX",
            observed_recipient=invoice.recipient, observed_amount_sun=invoice.amount_sun,
            independently_finalized=True, evidence_digest="c"*64,
            verified_owner_email=self.owner.email)
        self.command = uuid.uuid4()
        self.order = OrderRequest("order-1", "EURUSD", "buy", D("1"), stop_loss=D("99"))

    def submit(self, **overrides):
        params = dict(account_id=self.account.pk, owner=self.owner, command_id=self.command,
                      operation="submit", order=self.order)
        return record_command(**(params | overrides))

    def test_durable_replay_and_idempotency(self):
        first = self.submit()
        self.assertEqual(first.position_count, 1)
        self.assertEqual(self.submit(), first)
        self.assertEqual(account_snapshot(account_id=self.account.pk, owner=self.owner), first)
        self.assertEqual(PropSimulationEvent.objects.count(), 1)

    def test_conflicting_reuse_fails(self):
        self.submit()
        with self.assertRaises(ValidationError):
            self.submit(order=OrderRequest("order-2", "EURUSD", "buy", D("1"), stop_loss=D("99")))

    def test_modified_payload_fails_integrity_check(self):
        self.submit()
        event = PropSimulationEvent.objects.get()
        event.payload["quote"]["bid"] = "1000"
        event.save(update_fields=["payload"])
        with self.assertRaises(ValidationError):
            account_snapshot(account_id=self.account.pk, owner=self.owner)

    def test_disabled_service_and_missing_provider_cannot_write(self):
        with override_settings(MPW_SIMULATION_TRADING_ENABLED=False):
            with self.assertRaises(ValidationError):
                self.submit()
        with override_settings(MPW_SIMULATION_QUOTE_PROVIDER=None):
            with self.assertRaises(ValidationError):
                self.submit()
        self.assertFalse(PropSimulationEvent.objects.exists())

    def test_removed_tail_detected_against_persisted_head(self):
        self.submit()
        PropSimulationEvent.objects.all().delete()
        with self.assertRaises(ValidationError):
            account_snapshot(account_id=self.account.pk, owner=self.owner)

    def test_internal_quote_processing_closes_stop_and_persists_result(self):
        self.submit()
        def next_quote(*, account_id, symbol):
            return MarketQuote(symbol, D("97"), D("98"), "2026-11-19T00:00:02Z", 2)
        with override_settings(MPW_SIMULATION_QUOTE_PROVIDER=next_quote):
            result = advance_account_quotes(account_id=self.account.pk)
        self.assertEqual(result.position_count, 0)
        self.assertEqual(result.realized_pnl, D("-4"))
        self.assertEqual(account_snapshot(account_id=self.account.pk, owner=self.owner), result)
        self.account.refresh_from_db()
        self.assertEqual(self.account.event_head_sequence, 2)

    @override_settings(ALLOWED_HOSTS=["mojplaywin.com", "zomorodmelal.ir"],
                       MPW_SIMULATION_ALLOWED_SYMBOLS=("EURUSD",),
                       MPW_SIMULATION_WORKER_READY=True)
    def test_terminal_owner_scope_and_submission_without_browser_price(self):
        path = f"/moj-prop/account/{self.account.pk}/terminal/"
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(path, secure=True, HTTP_HOST="mojplaywin.com"),
                            "Virtual balance")
        self.assertEqual(self.client.get(path, secure=True, HTTP_HOST="zomorodmelal.ir").status_code, 404)
        self.assertEqual(self.client.get(path, secure=False, HTTP_HOST="mojplaywin.com").status_code, 404)
        body = {"operation":"submit", "command_id":str(uuid.uuid4()), "symbol":"EURUSD",
                "side":"buy", "quantity":"1", "stop_loss":"99", "take_profit":""}
        invalid = self.client.post(path, {**body, "price":"1"}, secure=True, HTTP_HOST="mojplaywin.com")
        self.assertContains(invalid, "Order could not be processed")
        self.assertFalse(PropSimulationEvent.objects.exists())
        self.assertEqual(self.client.post(path, body, secure=True, HTTP_HOST="mojplaywin.com").status_code, 302)
        self.assertEqual(PropSimulationEvent.objects.get().payload["quote"]["ask"], "101")
        outsider = get_user_model().objects.create_user(username="other-terminal", email="other@farmco.org")
        PropSimulationIdentity.objects.create(owner=outsider, email=outsider.email, verified_at=timezone.now())
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(path, secure=True, HTTP_HOST="mojplaywin.com").status_code, 404)
