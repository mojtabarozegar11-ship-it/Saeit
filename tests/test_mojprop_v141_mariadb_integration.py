"""Actual Django+MariaDB transaction checks on DISPOSABLE CI database only.

These tests are never part of source-only 835-case Python review.
A green result proves isolated schema and SQL behavior, NOT a live migration,
production recovery, independently authentic prices or legal paid readiness.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
import hashlib
import hmac
from threading import Barrier
import unittest

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, connections, transaction, close_old_connections
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from django.utils import timezone

from prop_firm.plan1_v14_social_or_50_terms import review_prospective_terms
from prop_firm.plan1_v141_persistence_models import PropV141SimState
from prop_firm.plan1_v141_virtual_tenant_models import PropV141VirtualBook, PropV141VirtualFill
from prop_firm.plan1_v141_virtual_tenant_fill_ledger import VirtualFill
from prop_firm.plan1_v141_atomic_virtual_fill_service import (
    DurableVirtualFillRejected, _payload, store_v141_virtual_fill,
)

FEED = "ci-authenticated-virtual-feed"
KEY_ID = "ci-test-hmac-key"
KEY = b"Z" * 32
SHA = "a" * 64


class IsolatedMariaDBVirtualBookTests(TransactionTestCase):
    """Real SQL checks including transaction rollback and row-lock concurrency."""

    databases = {"default"}

    def setUp(self):
        self.now = timezone.now()
        self.started = self.now - timedelta(days=1)
        self.owner = get_user_model().objects.create_user(username="mojprop-ci-owner")
        self.other = get_user_model().objects.create_user(username="mojprop-ci-other")
        self.state = self._state("CHALLENGE-CI-AAAAAAAAAAAAAAAA")
        self.book = self._book(self.state, self.owner, "TRADER-CI-A")

    def _state(self, challenge_ref):
        return PropV141SimState.objects.create(
            challenge_ref=challenge_ref,
            terms_sha256=review_prospective_terms().contract_candidate_sha256,
            trusted_source="ci-publisher-not-broker",
            trusted_key_id=KEY_ID,
            trusted_feed_source=FEED,
        )

    def _book(self, state, owner, trader_ref):
        return PropV141VirtualBook.objects.create(
            state=state, owner=owner, trader_ref=trader_ref,
            terms_sha256=state.terms_sha256,
            trusted_feed_source=FEED,
            evaluation_started_at=self.started,
        )

    def _event(self, book=None, *, seq=1, event_id=None, action="OPEN",
               price="3000.0000", qty="1.0000", phase=1):
        b = book or self.book
        return VirtualFill(
            trader_ref=b.trader_ref, challenge_ref=b.state.challenge_ref,
            event_id=event_id or f"CI-EVENT-{b.pk}-{seq}",
            sequence=seq, position_ref=f"CI-POSITION-{b.pk}",
            stage=phase, action=action, direction="BUY",
            symbol="XAUUSD", quantity_ounces=qty,
            price_usd_per_ounce=price, fee_usd="0.1000",
            executed_at_utc=self.started + timedelta(minutes=seq),
            feed_source=FEED, raw_event_sha256=SHA,
        )

    def _store(self, book, fill, *, user=None, signature=None):
        sig = signature if signature is not None else hmac.new(
            KEY, _payload(book, fill), hashlib.sha256
        ).hexdigest()
        return store_v141_virtual_fill(
            trusted_book_pk=book.pk,
            authenticated_site_user_pk=(user or book.owner).pk,
            fill=fill, ingress_signature_sha256=sig,
            server_owned_hmac_keys={KEY_ID: KEY},
            server_now=self.now,
        )

    def _raw_fill(self, **changes):
        fields = dict(
            book=self.book, sequence=1, event_id="CI-DB-RAW-EVENT",
            position_ref="CI-DB-RAW-POSITION", stage=1,
            action="OPEN", direction="BUY", symbol="XAUUSD",
            quantity_ounces=Decimal("1.0000"),
            price_usd_per_ounce=Decimal("3000.0000"),
            fee_usd=Decimal("0.1000"),
            executed_at_utc=self.started + timedelta(minutes=1),
            feed_source=FEED, raw_event_sha256=SHA,
        )
        fields.update(changes)
        return fields

    def test_01_real_mariadb_and_innodb_for_new_tables(self):
        self.assertEqual(connection.vendor, "mysql")
        with connection.cursor() as c:
            c.execute("SELECT VERSION(), @@SESSION.sql_mode")
            version, sql_mode = c.fetchone()
            self.assertIn("MariaDB", version)
            self.assertTrue(("STRICT_TRANS_TABLES" in sql_mode) or
                            ("STRICT_ALL_TABLES" in sql_mode))
            for model in (PropV141SimState, PropV141VirtualBook, PropV141VirtualFill):
                c.execute(
                    "SELECT ENGINE FROM information_schema.tables "
                    "WHERE table_schema=DATABASE() AND table_name=%s",
                    [model._meta.db_table],
                )
                row = c.fetchone()
                self.assertIsNotNone(row, model._meta.db_table)
                self.assertEqual(row[0].upper(), "INNODB")

    def test_02_real_migrations_0009_and_0010_applied(self):
        applied = MigrationRecorder(connection).applied_migrations()
        self.assertIn(("prop_firm", "0009_v141_sim_replay_journal"), applied)
        self.assertIn(("prop_firm", "0010_v141_virtual_tenant_books"), applied)
        self.assertTrue(apps.get_model("prop_firm", "PropV141VirtualBook"))

    def test_03_real_sql_insert_then_idempotent_authenticated_replay(self):
        e = self._event()
        first = self._store(self.book, e)
        second = self._store(self.book, e)
        self.assertFalse(first.idempotent_replay)
        self.assertTrue(second.idempotent_replay)
        self.assertEqual(first.history_sha256, second.history_sha256)
        self.assertEqual(PropV141VirtualFill.objects.count(), 1)
        self.book.refresh_from_db()
        self.assertEqual(self.book.last_sequence, 1)

    def test_04_wrong_authenticated_website_owner_denied(self):
        with self.assertRaises(DurableVirtualFillRejected):
            self._store(self.book, self._event(), user=self.other)
        self.assertEqual(PropV141VirtualFill.objects.count(), 0)

    def test_05_invalid_hmac_denied_in_transaction(self):
        with self.assertRaises(DurableVirtualFillRejected):
            self._store(self.book, self._event(), signature="0" * 64)
        self.assertEqual(PropV141VirtualFill.objects.count(), 0)

    def test_06_global_unique_event_cannot_be_used_by_second_customer(self):
        e = self._event(event_id="CI-SAME-GLOBAL-FILL")
        self._store(self.book, e)
        state2 = self._state("CHALLENGE-CI-BBBBBBBBBBBBBBBB")
        book2 = self._book(state2, self.other, "TRADER-CI-B")
        with self.assertRaises(DurableVirtualFillRejected):
            self._store(book2, self._event(book2, event_id=e.event_id))
        self.assertEqual(PropV141VirtualFill.objects.count(), 1)

    def test_07_database_unique_book_sequence_enforced(self):
        PropV141VirtualFill.objects.create(**self._raw_fill())
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PropV141VirtualFill.objects.create(
                    **self._raw_fill(event_id="CI-DIFFERENT-DB-EVENT")
                )
        self.assertEqual(PropV141VirtualFill.objects.count(), 1)

    def test_08_database_rejects_negative_quantity(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PropV141VirtualFill.objects.create(
                    **self._raw_fill(quantity_ounces=Decimal("-1.0000"))
                )
        self.assertEqual(PropV141VirtualFill.objects.count(), 0)

    def test_09_state_book_one_to_one_database_constraint(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._book(self.state, self.other, "TRADER-CI-CONFLICT")
        self.assertEqual(PropV141VirtualBook.objects.count(), 1)

    def test_10_outer_transaction_rollback_restores_event_and_head(self):
        with self.assertRaisesRegex(RuntimeError, "intentional rollback"):
            with transaction.atomic():
                self._store(self.book, self._event())
                raise RuntimeError("intentional rollback")
        self.assertEqual(PropV141VirtualFill.objects.count(), 0)
        self.book.refresh_from_db()
        self.assertEqual(self.book.last_sequence, 0)
        self.assertEqual(self.book.last_history_sha256, "")

    def test_11_accepted_stage_one_rejects_new_signed_fill(self):
        self._store(self.book, self._event())
        self.state.last_phase_one_accepted_at = self.now
        self.state.last_phase_one_evidence_sha256 = SHA
        self.state.save(update_fields=[
            "last_phase_one_accepted_at", "last_phase_one_evidence_sha256",
        ])
        with self.assertRaises(DurableVirtualFillRejected):
            self._store(self.book, self._event(seq=2,action="CLOSE",price="3001"))
        self.assertEqual(PropV141VirtualFill.objects.count(), 1)

    def test_12_stage_two_rejected_without_accepted_checkpoint(self):
        self.book.max_unlocked_stage = 2
        self.book.save(update_fields=["max_unlocked_stage"])
        self.state.last_phase_two_started_at = self.started + timedelta(hours=2)
        self.state.save(update_fields=["last_phase_two_started_at"])
        with self.assertRaises(DurableVirtualFillRejected):
            self._store(self.book, self._event(phase=2))
        self.assertEqual(PropV141VirtualFill.objects.count(), 0)

    def test_13_two_concurrent_identical_appends_serialize_under_row_lock(self):
        e = self._event(event_id="CI-CONCURRENT-EVENT")
        sig = hmac.new(KEY, _payload(self.book,e), hashlib.sha256).hexdigest()
        book_id,owner_id = self.book.pk,self.owner.pk
        barrier = Barrier(2, timeout=10)

        def attempt():
            close_old_connections()
            try:
                barrier.wait()
                return store_v141_virtual_fill(
                    trusted_book_pk=book_id,
                    authenticated_site_user_pk=owner_id,
                    fill=e, ingress_signature_sha256=sig,
                    server_owned_hmac_keys={KEY_ID:KEY},
                    server_now=self.now,
                ).idempotent_replay
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda ignored: attempt(), range(2)))
        self.assertCountEqual(results, [False, True])
        self.assertEqual(PropV141VirtualFill.objects.count(),1)
        self.book.refresh_from_db()
        self.assertEqual(self.book.last_sequence,1)


if __name__ == "__main__":
    unittest.main()
