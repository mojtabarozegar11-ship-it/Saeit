"""Regression: failed Moj Prop login codes consume an attempt even when rejected.

Offline test. It mocks the dedicated ORM and models transaction rollback behavior.
No real account, email, financial backend, HTTP or live database is touched.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from prop_firm.simulation_identity_adapter import (
    IdentityAdapterClosed,
    _scoped_digest,
    consume_login_challenge,
)
from prop_firm.models import PropSimulationLoginChallenge
from config.mojprop_db_router import MOJPROP_DB_ALIAS

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
SECRET = "isolated-regression-only-digest-secret-at-least-32-characters"
REF = "MOJPROP-LOGIN-CHALLENGE-REFERENCE"
RIGHT_CODE = "0123456789abcdef0123456789abcdef"


@override_settings(MPW_MOJPROP_IDENTITY_DIGEST_SECRET=SECRET)
class LoginFailedAttemptAtomicRegressionTests(SimpleTestCase):
    def setUp(self):
        digest = _scoped_digest(SECRET.encode(), "challenge", REF + ":" + RIGHT_CODE)
        self.row = SimpleNamespace(
            identity_id=17,
            challenge_ref=REF,
            code_digest=digest,
            expires_at=NOW + timedelta(minutes=10),
            consumed_at=None,
            attempt_count=0,
            save=Mock(),
        )
        self.manager = Mock()
        self.manager.using.return_value.select_for_update.return_value.get.return_value = self.row
        self.transactions = []

        @contextmanager
        def fake_transaction(*, using):
            self.assertEqual(using, MOJPROP_DB_ALIAS)
            self.transactions.append(using)
            before = (self.row.attempt_count, self.row.consumed_at)
            try:
                yield
            except BaseException:
                # Models the critical Django atomic rollback of a failed write.
                self.row.attempt_count, self.row.consumed_at = before
                raise

        self.object_patch = patch.object(
            PropSimulationLoginChallenge, "objects", self.manager
        )
        self.atomic_patch = patch(
            "prop_firm.simulation_identity_adapter.transaction.atomic", fake_transaction
        )
        self.object_patch.start()
        self.atomic_patch.start()
        self.addCleanup(self.atomic_patch.stop)
        self.addCleanup(self.object_patch.stop)

    def _consume(self, code, **kwargs):
        return consume_login_challenge(REF, code, now=NOW, **kwargs)

    def test_wrong_code_commits_attempt_before_error(self):
        with self.assertRaisesRegex(IdentityAdapterClosed, "invalid or expired challenge"):
            self._consume("WRONG-LOGIN-CODE")
        self.assertEqual(self.row.attempt_count, 1)
        self.assertIsNone(self.row.consumed_at)
        self.row.save.assert_called_once_with(
            using=MOJPROP_DB_ALIAS, update_fields=["attempt_count"]
        )
        self.manager.using.assert_called_with(MOJPROP_DB_ALIAS)

    def test_expired_correct_code_consumes_attempt_without_session(self):
        self.row.expires_at = NOW - timedelta(microseconds=1)
        with self.assertRaisesRegex(IdentityAdapterClosed, "invalid or expired challenge"):
            self._consume(RIGHT_CODE)
        self.assertEqual(self.row.attempt_count, 1)
        self.assertIsNone(self.row.consumed_at)

    def test_wrong_codes_hit_persistent_five_attempt_lockout(self):
        for attempt in range(5):
            with self.assertRaises(IdentityAdapterClosed):
                self._consume("invalid" + str(attempt))
            self.assertEqual(self.row.attempt_count, attempt + 1)
        with self.assertRaisesRegex(IdentityAdapterClosed, "attempt limit reached"):
            self._consume(RIGHT_CODE)
        self.assertEqual(self.row.attempt_count, 5)
        self.assertIsNone(self.row.consumed_at)
        self.assertEqual(self.row.save.call_count, 5)

    def test_correct_code_consumed_once_only(self):
        identity_id = self._consume(RIGHT_CODE)
        self.assertEqual(identity_id, 17)
        self.assertEqual(self.row.consumed_at, NOW)
        self.assertEqual(self.row.attempt_count, 0)
        self.row.save.assert_called_once_with(
            using=MOJPROP_DB_ALIAS, update_fields=["consumed_at"]
        )
        with self.assertRaisesRegex(IdentityAdapterClosed, "already consumed"):
            self._consume(RIGHT_CODE)

    def test_database_save_exception_rolls_back_and_rejects(self):
        self.row.save.side_effect = RuntimeError("database unavailable")
        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            self._consume("bad")
        self.assertEqual(self.row.attempt_count, 0)
        self.assertIsNone(self.row.consumed_at)

    def test_reject_invalid_challenge_parameters_without_write(self):
        with self.assertRaises(IdentityAdapterClosed):
            self._consume("")
        with self.assertRaises(IdentityAdapterClosed):
            self._consume("bad", max_attempts=11)
        self.row.save.assert_not_called()
        self.assertEqual(self.transactions, [])


if __name__ == "__main__":
    import unittest
    unittest.main()
