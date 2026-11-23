"""Run journal integration cases in a dedicated isolated Django process.

The project's two general CI configurations do not both enable the isolated
router and database alias. Never relax the database allowlist or change
production settings merely to run these integration cases.
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest


if __name__ != "__main__":
    class JournalIsolatedProcessTests(unittest.TestCase):
        def test_journal_integration_suite(self):
            env = os.environ.copy()
            env.pop("DJANGO_SETTINGS_MODULE", None)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            process = subprocess.run(
                [sys.executable, "-m", "prop_firm.test_simulation_execution_journal_20261120"],
                cwd=Path(__file__).resolve().parent.parent,
                env=env, capture_output=True, text=True, timeout=180,
            )
            output = process.stdout + "\n" + process.stderr
            self.assertEqual(process.returncode, 0, output)
            self.assertIn("Ran 25 tests", output)
            self.assertIn("OK", output)
else:
    from django.conf import settings
    settings.configure(
        SECRET_KEY="journal-isolated-ci-only",
        # Legacy prop_firm migrations depend on AUTH_USER_MODEL; include
        # their migration-only dependencies in this isolated SQLite process.
        # The production router still bars non-simulation tables from mojprop.
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "prop_firm.apps.MojPropConfig",
        ],
        DATABASES={
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
            "mojprop": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:",
                        "TEST": {"DEPENDENCIES": []}},
        },
        DATABASE_ROUTERS=["config.mojprop_db_router.MojPropDatabaseRouter"],
        USE_TZ=True,
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )
    import django
    django.setup()

    from dataclasses import replace
    from datetime import timedelta
    from decimal import Decimal as D

    from django.test import TestCase
    from django.utils import timezone

    from prop_firm.models import PropSimulationAccount, PropSimulationEvent, PropSimulationIdentity, PropSimulationInvoiceOwner
    from prop_firm.simulation_engine import ClosedExecutionRecord, MarketQuote, OrderRequest, SimulationEngine
    from prop_firm.simulation_journal_accounting import flush_engine_closures, observed_daily_accounting
    from zoneinfo import ZoneInfo
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


        def test_engine_flush_and_observed_accounting(self):
            e=SimulationEngine(commission_per_unit=D("0.25"))
            opened=self.record.opened_at.isoformat()
            closed=self.record.closed_at.isoformat()
            e.submit(OrderRequest("engine-a","A","buy",D("1"),stop_loss=D("90")),
                     MarketQuote("A",D("99"),D("100"),opened,1))
            e.close("engine-a",MarketQuote("A",D("105"),D("106"),closed,2))
            self.assertEqual(flush_engine_closures(account_ref=self.account.account_ref,engine=e),(1,))
            self.assertEqual(flush_engine_closures(account_ref=self.account.account_ref,engine=e),(1,))
            self.assertEqual(self.rows().count(),1)
            for zone in ("UTC","Asia/Tokyo"):
                result=observed_daily_accounting(account_ref=self.account.account_ref,day_timezone=zone)
                day=self.record.closed_at.astimezone(ZoneInfo(zone)).date()
                self.assertEqual(result["observed_daily_net_usd"],{day:D("4.75")})
                self.assertEqual(result["observed_net_usd"],D("4.75"))
                self.assertEqual(result["observed_closures"],1)
                self.assertFalse(result["complete_history_verified"])
                self.assertFalse(result["eligible_for_pass"])

        def test_engine_flush_mismatch_fails_closed(self):
            e=SimulationEngine()
            e.realized_pnl=D("1")
            with self.assertRaises(JournalConflict):
                flush_engine_closures(account_ref=self.account.account_ref,engine=e)
            self.assertEqual(self.rows().count(),0)

        def test_empty_history_does_not_imply_verified_zero_days(self):
            result=observed_daily_accounting(account_ref=self.account.account_ref,day_timezone="UTC")
            self.assertEqual(result["observed_daily_net_usd"],{})
            self.assertEqual(result["observed_closures"],0)
            self.assertFalse(result["complete_history_verified"])
            self.assertFalse(result["eligible_for_pass"])

        def test_accounting_rejects_modified_digest(self):
            self.append(self.record)
            self.rows().update(payload_digest="0"*64)
            with self.assertRaises(JournalConflict):
                observed_daily_accounting(account_ref=self.account.account_ref,day_timezone="UTC")


        def make_large_engine(self):
            e=SimulationEngine()
            for i in range(501):
                e.submit(OrderRequest("bulk-"+str(i),"A","buy",D("1"),stop_loss=D("90")),
                         MarketQuote("A",D("99"),D("100"),self.record.opened_at.isoformat(),2*i+1))
                e.close("bulk-"+str(i),MarketQuote("A",D("100"),D("101"),
                                                 self.record.opened_at.isoformat(),2*i+2))
            self.assertEqual(e.closed_trade_count,501)
            return e

        def test_flush_more_than_one_batch_and_retry(self):
            e=self.make_large_engine()
            expected=tuple(range(1,502))
            self.assertEqual(flush_engine_closures(account_ref=self.account.account_ref,engine=e),expected)
            self.assertEqual(flush_engine_closures(account_ref=self.account.account_ref,engine=e),expected)
            self.assertEqual(self.rows().count(),501)
            result=observed_daily_accounting(account_ref=self.account.account_ref,day_timezone="UTC")
            self.assertEqual(result["observed_closures"],501)
            self.assertFalse(result["eligible_for_pass"])

        def test_second_batch_conflict_rolls_back_first(self):
            e=self.make_large_engine()
            conflicting=replace(e.closed_execution_records[-1],reason="conflicting fixture")
            self.append(conflicting)
            with self.assertRaises(JournalConflict):
                flush_engine_closures(account_ref=self.account.account_ref,engine=e)
            self.assertEqual(self.rows().count(),1)
            self.assertEqual(self.rows().get().payload["reason"],"conflicting fixture")


    from django.test.runner import DiscoverRunner
    raise SystemExit(bool(DiscoverRunner(verbosity=2).run_tests(
        ["__main__.ExecutionJournalTests", "prop_firm.checkpoint_cases_20261121.CheckpointRecoveryTests"])))
