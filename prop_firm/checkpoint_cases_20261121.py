"""Isolated DB checkpoint tests, loaded only by the journal child runner."""
from datetime import timedelta
from decimal import Decimal as D
from copy import deepcopy

from django.test import TestCase
from django.utils import timezone

from prop_firm.models import (
    PropSimulationAccount, PropSimulationEvent,
    PropSimulationIdentity, PropSimulationInvoiceOwner,
)
from prop_firm.simulation_engine import SimulationEngine, OrderRequest, MarketQuote
from prop_firm.simulation_checkpoint import export_checkpoint, recover_quarantined_engine
from prop_firm.simulation_checkpoint_store import (
    capture_unattested_checkpoint, inspect_checkpoint_after_restart, SOURCE,
)
from prop_firm.simulation_execution_journal import JournalConflict, persist_closed_executions


DB="mojprop"


class CheckpointRecoveryTests(TestCase):
    databases={DB}

    def setUp(self):
        now=timezone.now()
        ident=PropSimulationIdentity.objects.using(DB).create(
            subject_key="checkpoint-fixture", email_digest="c"*64,status="active")
        owner=PropSimulationInvoiceOwner.objects.using(DB).create(
            identity=ident,invoice_ref="checkpoint-fixture-invoice",
            buyer_email_digest=ident.email_digest,settlement_reference="fixture-only",
            settlement_verified=True,contract_version="2026-11-19/simulation-v1")
        self.account=PropSimulationAccount.objects.using(DB).create(
            identity=ident,invoice_owner=owner,account_ref="checkpoint-fixture-account",
            kind="challenge",status="active",opened_at=now-timedelta(hours=2))
        self.t1=now-timedelta(hours=1)
        self.t2=now-timedelta(minutes=30)
        self.t3=now-timedelta(minutes=10)

    def q(self,symbol,bid,ask,sequence,when=None):
        return MarketQuote(symbol,D(bid),D(ask),
                           (when or self.t1).isoformat(),sequence)

    def buy(self,ref,symbol="A",limit=None):
        return OrderRequest(ref,symbol,"buy",D("1"),
                            order_type="limit" if limit is not None else "market",
                            limit_price=D(limit) if limit is not None else None,
                            stop_loss=D("90"))

    def engine_open_pending(self):
        e=SimulationEngine()
        self.assertEqual(e.submit(self.buy("open-1"),self.q("A","100","101",1)).status,"filled")
        self.assertEqual(e.submit(self.buy("pending-1","B",limit="95"),
                                  self.q("B","100","101",2)).status,"pending")
        return e

    def capture(self,e):
        return capture_unattested_checkpoint(account_ref=self.account.account_ref,engine=e)

    def restore(self):
        return inspect_checkpoint_after_restart(account_ref=self.account.account_ref)

    def test_restore_open_position_and_pending_order_always_blocked(self):
        e=self.engine_open_pending()
        seq=self.capture(e)
        self.assertEqual(seq,1)
        recovered=self.restore()
        self.assertFalse(recovered.resumable)
        self.assertTrue(recovered.engine.blocked)
        self.assertEqual(set(recovered.engine.positions),{"open-1"})
        self.assertEqual(set(recovered.engine.pending),{"pending-1"})
        self.assertEqual(recovered.engine.last_quote_sequence,2)
        self.assertEqual(recovered.engine.last_quote_time,e.last_quote_time)
        self.assertEqual(recovered.engine.snapshot().equity,e.snapshot().equity)
        self.assertEqual(recovered.engine.submit(self.buy("new-1"),
                          self.q("A","100","101",3)).reason,"quarantined_checkpoint")

    def test_recover_closed_execution_and_idempotent_capture(self):
        e=SimulationEngine()
        e.submit(self.buy("closed-1"),self.q("A","100","101",1))
        e.close("closed-1",self.q("A","105","106",2,self.t2))
        e.submit(self.buy("open-2"),self.q("A","105","106",3,self.t3))
        seq=self.capture(e)
        self.assertEqual(self.capture(e),seq)
        recovered=self.restore()
        self.assertEqual(recovered.closure_count,1)
        self.assertEqual(recovered.engine.closed_trade_count,1)
        self.assertEqual(recovered.engine.realized_pnl,D("4"))
        self.assertEqual(recovered.engine.closed_execution_records[0].reason,"manual")
        self.assertEqual(set(recovered.engine.positions),{"open-2"})
        self.assertTrue(recovered.engine.blocked)
        self.assertEqual(PropSimulationEvent.objects.using(DB).filter(account=self.account).count(),2)

    def test_latest_checkpoint_selected(self):
        e=SimulationEngine()
        self.assertEqual(self.capture(e),1)
        e.process_quote(self.q("A","100","101",1))
        self.assertEqual(self.capture(e),2)
        self.assertEqual(self.restore().event_sequence,2)
        self.assertEqual(self.restore().engine.last_quote_sequence,1)

    def test_corrupted_digest_rejected(self):
        self.capture(self.engine_open_pending())
        PropSimulationEvent.objects.using(DB).filter(account=self.account,source=SOURCE).update(
            payload_digest="0"*64)
        with self.assertRaises(JournalConflict):
            self.restore()

    def test_invalid_position_protection_is_rejected(self):
        state=export_checkpoint(self.engine_open_pending())
        corrupted=deepcopy(state)
        corrupted["positions"][0]["stop_loss"]="110"
        with self.assertRaises(JournalConflict):
            recover_quarantined_engine(corrupted,closed_records=())

    def test_missing_checkpoint_not_resumed(self):
        with self.assertRaises(JournalConflict):
            self.restore()

    def test_checkpoint_does_not_autoresume_closed_account(self):
        self.capture(self.engine_open_pending())
        PropSimulationAccount.objects.using(DB).filter(pk=self.account.pk).update(status="closed")
        self.assertTrue(self.restore().engine.blocked)

    def test_conflicting_journal_after_checkpoint_is_rejected(self):
        e=SimulationEngine()
        e.submit(self.buy("closed-1"),self.q("A","100","101",1))
        e.close("closed-1",self.q("A","105","106",2,self.t2))
        self.capture(e)
        from dataclasses import replace
        extra=replace(e.closed_execution_records[0],order_id="new-closed")
        persist_closed_executions(account_ref=self.account.account_ref,records=[extra])
        with self.assertRaises(JournalConflict):
            self.restore()

    def test_checkpoint_metadata_wrong_account_rejected(self):
        e=self.engine_open_pending()
        self.capture(e)
        rec=PropSimulationEvent.objects.using(DB).get(account=self.account,source=SOURCE)
        p=deepcopy(rec.payload)
        p["account_ref"]="other-account"
        PropSimulationEvent.objects.using(DB).filter(pk=rec.pk).update(payload=p)
        with self.assertRaises(JournalConflict):
            self.restore()


    def test_quarantined_engine_rejects_feed_updates_and_closure(self):
        self.capture(self.engine_open_pending())
        recovered=self.restore().engine
        before=recovered.snapshot()
        with self.assertRaisesRegex(ValueError,"quarantined_checkpoint"):
            recovered.process_quote(self.q("A","80","81",3,self.t2))
        with self.assertRaisesRegex(ValueError,"quarantined_checkpoint"):
            recovered.close("open-1",self.q("A","80","81",3,self.t2))
        self.assertEqual(recovered.snapshot(),before)
        self.assertEqual(recovered.last_quote_sequence,2)

    def test_quarantined_state_cannot_be_captured_again(self):
        self.capture(self.engine_open_pending())
        recovered=self.restore().engine
        with self.assertRaises(JournalConflict):
            self.capture(recovered)
        self.assertEqual(PropSimulationEvent.objects.using(DB).filter(
            account=self.account,source=SOURCE).count(),1)
