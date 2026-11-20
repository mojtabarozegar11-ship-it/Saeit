from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

from django.test import TestCase
from django.utils import timezone

from prop_firm.models import PropSimulationAccount, PropSimulationEvent, PropSimulationIdentity, PropSimulationInvoiceOwner
from prop_firm.simulation_engine import ClosedExecutionRecord
from prop_firm.simulation_execution_journal import JournalConflict, persist_closed_executions, read_closed_execution_payloads

DB="mojprop"


class ExecutionJournalTests(TestCase):
    databases={DB}

    def setUp(self):
        now=timezone.now()
        identity=PropSimulationIdentity.objects.using(DB).create(
            subject_key="journal-test",email_digest="a"*64,status="active")
        owner=PropSimulationInvoiceOwner.objects.using(DB).create(
            identity=identity,invoice_ref="journal-test-invoice",buyer_email_digest=identity.email_digest,
            settlement_reference="fixture-only",settlement_verified=True,contract_version="starter30-simulation-v1")
        self.account=PropSimulationAccount.objects.using(DB).create(
            identity=identity,invoice_owner=owner,account_ref="journal-test-account",
            kind="challenge",status="active",opened_at=now-timedelta(hours=2))
        self.record=ClosedExecutionRecord("order-1","A","buy",D("1"),D("100"),D("105"),1,2,
            now-timedelta(hours=1),now-timedelta(minutes=5),D("5"),D("0.25"),D("4.75"),"manual")

    def append(self,*records):
        return persist_closed_executions(account_ref=self.account.account_ref,records=records)

    def rows(self):
        return PropSimulationEvent.objects.using(DB).filter(account=self.account)

    def test_write_and_retry(self):
        self.assertEqual(self.append(self.record),(1,))
        self.assertEqual(self.append(self.record),(1,))
        self.assertEqual(self.rows().count(),1)
        row,=read_closed_execution_payloads(account_ref=self.account.account_ref)
        self.assertEqual(row[1]["net_pnl"],"4.75")
        self.assertEqual(row[1]["provenance"],"unattested")

    def test_conflicting_replay(self):
        self.append(self.record)
        with self.assertRaises(JournalConflict):
            self.append(replace(self.record,reason="different"))
        self.assertEqual(self.rows().count(),1)

    def test_atomic_invalid_second_record(self):
        with self.assertRaises(JournalConflict):
            self.append(self.record,replace(self.record,order_id="order-2",net_pnl=D("500")))
        self.assertEqual(self.rows().count(),0)

    def test_read_detects_digest_mismatch(self):
        self.append(self.record)
        self.rows().update(payload_digest="0"*64)
        with self.assertRaises(JournalConflict):
            read_closed_execution_payloads(account_ref=self.account.account_ref)

    def test_sequence_pagination(self):
        self.assertEqual(self.append(self.record,replace(self.record,order_id="order-2")),(1,2))
        rows=read_closed_execution_payloads(account_ref=self.account.account_ref,after_sequence=1)
        self.assertEqual([r[0] for r in rows],[2])

    def test_inactive_account_rejects_new_write(self):
        PropSimulationAccount.objects.using(DB).filter(pk=self.account.pk).update(status="closed")
        with self.assertRaises(JournalConflict):
            self.append(self.record)
        self.assertEqual(self.rows().count(),0)

    def test_duplicate_batch_rolls_back(self):
        with self.assertRaises(JournalConflict):
            self.append(self.record,self.record)
        self.assertEqual(self.rows().count(),0)

    def test_reject_time_outside_account(self):
        with self.assertRaises(JournalConflict):
            self.append(replace(self.record,opened_at=self.account.opened_at-timedelta(seconds=1)))
        self.assertEqual(self.rows().count(),0)
