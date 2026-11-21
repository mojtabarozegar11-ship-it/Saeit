"""Production-closed, DB-backed OTP request cooldown across browser sessions.

No database, SMTP, production session or customer account is created. The
actual private buyer portal code is exercised with isolated, bound mocks.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from prop_firm import customer_portal_views as portal


NOW = datetime(2026, 11, 21, 8, 0, 0, tzinfo=timezone.utc)


class MojPropDbSharedOtpThrottleTests(SimpleTestCase):
    def _make_request(self):
        request = RequestFactory().post(
            "/mojprop-buyer-portal/",
            {"action": "request", "email": "buyer@example.org"},
        )
        request.session = {}
        return request

    def _run(self, *, count, last_issued, send_ok=True):
        request = self._make_request()
        identity_manager = MagicMock()
        identity_manager.using.return_value.filter.return_value.first.return_value = SimpleNamespace(pk=71)
        identity_manager.using.return_value.select_for_update.return_value.get.return_value = SimpleNamespace(pk=71)
        challenge_manager = MagicMock()
        scope = challenge_manager.using.return_value.filter.return_value
        scope.count.return_value = count
        scope.order_by.return_value.values_list.return_value.first.return_value = last_issued
        issued = SimpleNamespace(
            challenge_ref="MPS30-OTP-TEST-NOT-A-REAL-CODE",
            code="isolated-offline-only-secret",
            expires_at=NOW + timedelta(minutes=10),
        )

        @contextmanager
        def atomic(*, using):
            self.assertEqual(using, portal.MOJPROP_DB_ALIAS)
            yield

        with (
            patch.object(portal.timezone, "now", return_value=NOW),
            patch.object(portal, "normalize_email", return_value="buyer@example.org"),
            patch.object(portal, "_identity_keys", return_value=("a" * 64, "b" * 64)),
            patch.object(portal, "_paid_learner_accounts", return_value=[{"id": "fake-offline"}]),
            patch.object(portal.PropSimulationIdentity, "objects", identity_manager),
            patch.object(portal.PropSimulationLoginChallenge, "objects", challenge_manager),
            patch.object(portal.transaction, "atomic", atomic),
            patch.object(portal, "issue_login_challenge", return_value=issued) as issue,
            patch.object(portal, "send_mail", return_value=(1 if send_ok else 0)) as mail,
            patch.object(portal, "_login_page", return_value=HttpResponse("Generic no-account-proof")) as generic_page,
        ):
            response = portal._request_code(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"Generic no-account-proof")
        self.assertEqual(identity_manager.using.call_args.args, (portal.MOJPROP_DB_ALIAS,))
        identity_manager.using.return_value.select_for_update.assert_called_once()
        self.assertEqual(challenge_manager.using.return_value.filter.return_value.count.call_count, 1)
        return request, issue, mail

    def test_recent_code_is_denied_across_new_browser_session(self):
        req, issue, mail = self._run(count=1, last_issued=NOW - timedelta(seconds=20))
        issue.assert_not_called()
        mail.assert_not_called()
        self.assertIn(portal._SESSION_CHALLENGE, req.session)
        self.assertNotIn(portal._SESSION_ID, req.session)

    def test_three_issued_codes_are_limited_in_15min(self):
        req, issue, mail = self._run(count=3, last_issued=NOW - timedelta(minutes=3))
        issue.assert_not_called()
        mail.assert_not_called()
        self.assertNotIn(portal._SESSION_ID, req.session)

    def test_shared_db_allows_new_code_after_60_second_window(self):
        req, issue, mail = self._run(count=1, last_issued=NOW - timedelta(seconds=61))
        issue.assert_called_once_with(71)
        mail.assert_called_once()
        self.assertEqual(req.session[portal._SESSION_CHALLENGE], "MPS30-OTP-TEST-NOT-A-REAL-CODE")
        self.assertNotIn(portal._SESSION_ID, req.session)

    def test_no_previous_code_allows_first_issued_code_only_for_settled_account(self):
        req, issue, mail = self._run(count=0, last_issued=None)
        issue.assert_called_once_with(71)
        mail.assert_called_once()

    def test_email_transport_failure_does_not_mark_browser_authenticated(self):
        req, issue, mail = self._run(count=0, last_issued=None, send_ok=False)
        issue.assert_called_once_with(71)
        mail.assert_called_once()
        self.assertNotEqual(req.session.get(portal._SESSION_CHALLENGE), "MPS30-OTP-TEST-NOT-A-REAL-CODE")
        self.assertNotIn(portal._SESSION_ID, req.session)


if __name__ == "__main__":
    import unittest
    unittest.main()
