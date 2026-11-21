"""Fail-closed MOJ PROP paid-buyer journal portal contract.

Strictly offline: no paid invoice, email, customer, live host, TRON transfer,
payment entitlement or private data is created by these tests.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings

from prop_firm import customer_portal_views as portal
from scripts.mojprop_starter30 import assess_journal
from scripts.mojprop_starter30_journal_csv import parse_journal_csv

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "config/settings.py"
URLS = ROOT / "config/urls.py"
APP = ROOT / "prop_firm/customer_portal_views.py"
GATES = {
    "MPW_MOJPROP_BUYER_PORTAL_APPROVED": True,
    "MPW_MOJPROP_BUYER_TRANSACTIONAL_EMAIL_APPROVED": True,
    "MPW_MOJPROP_BUYER_SHARED_RATE_LIMIT_VERIFIED": True,
    "MPW_MOJPROP_BUYER_DELIVERY_RECOVERY_VERIFIED": True,
    "SESSION_COOKIE_SECURE": True,
    "CSRF_COOKIE_SECURE": True,
}


class MojPropPrivateEducationalPortalTests(SimpleTestCase):
    def test_buyer_portal_is_deny_by_default_and_never_emails(self):
        request = RequestFactory().get("/mojprop-buyer-portal/")
        with override_settings(**{**GATES, "MPW_MOJPROP_BUYER_PORTAL_APPROVED": False}):
            with patch.object(portal, "release_is_open", return_value=True):
                with patch.object(portal, "send_mail") as mail:
                    with self.assertRaises(Http404):
                        portal.buyer_portal(request)
                    mail.assert_not_called()

    def test_each_independent_gate_required(self):
        for flag in GATES:
            with self.subTest(flag=flag), override_settings(**{**GATES, flag: False}):
                with patch.object(portal, "release_is_open", return_value=True):
                    with self.assertRaises(Http404):
                        portal._require_authorized_release()

    @override_settings(**GATES)
    def test_release_must_also_be_actual_live_starter30(self):
        with patch.object(portal, "release_is_open", return_value=False):
            with self.assertRaises(Http404):
                portal._require_authorized_release()
        with patch.object(portal, "release_is_open", return_value=True):
            portal._require_authorized_release()

    def test_private_html_has_no_external_assets_and_cannot_cache(self):
        request = RequestFactory().get("/mojprop-buyer-portal/")
        request.session = {}
        response = portal._page(request, "Private education", "<p>Personal data</p>")
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertNotIn("<script", html)
        self.assertNotIn("utm_", html)
        self.assertIn("csrfmiddlewaretoken", portal._csrf_field(request))

    def test_direct_case_link_without_authenticated_session_shows_login(self):
        request = RequestFactory().get("/mojprop-buyer-portal/", {"case": "MPS30-"+"A"*20})
        request.session = {}
        with patch.object(portal.PropSimulationEvent, "objects") as events:
            response = portal._report(request, "MPS30-" + "A" * 20)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Secure Starter30 sign-in", response.content)
            events.assert_not_called()

    def test_unknown_challenge_is_generic_and_never_authenticates(self):
        request = RequestFactory().post(
            "/mojprop-buyer-portal/", {"action": "verify", "code": "not-the-code"}
        )
        request.session = {portal._SESSION_CHALLENGE: "dummy-random-reference"}
        with patch.object(
            portal, "consume_login_challenge",
            side_effect=ObjectDoesNotExist("not found"),
        ):
            result = portal._verify_code(request)
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"Code invalid or expired", result.content)
        self.assertNotIn(portal._SESSION_ID, request.session)

    def test_bad_report_reference_is_not_queried_even_when_logged_in(self):
        request = RequestFactory().get("/mojprop-buyer-portal/")
        request.session = {portal._SESSION_ID: 42}
        with patch.object(portal.PropSimulationEvent, "objects") as events:
            with self.assertRaises(Http404):
                portal._report(request, "../../unauthorized")
            events.assert_not_called()

    def test_user_journal_upload_without_identity_performs_no_write(self):
        request = RequestFactory().post("/mojprop-buyer-portal/", {"action": "journal"})
        request.session = {}
        with patch.object(portal.PropSimulationEvent, "objects") as events:
            result = portal._journal(request)
            self.assertEqual(result.status_code, 200)
            events.assert_not_called()

    def test_bounded_training_csv_cannot_claim_real_trading_or_reward(self):
        sample = (
            b"session,closing_equity_usd,risk_plan_recorded,reflection_recorded\n"
            b"1,1000.00,yes,yes\n"
        )
        rows = parse_journal_csv(sample)
        result = assess_journal(rows)
        self.assertEqual(len(rows), 1)
        self.assertEqual(result["status"], "incomplete_training")
        self.assertFalse(result["payment_recorded"])
        self.assertFalse(result["trades_executed"])
        self.assertFalse(result["funded_account_earned"])

    def test_only_specific_paid_starter30_invoice_unlocks_educational_accounts(self):
        with patch.object(portal.PropSimulationAccount, "objects") as manager:
            manager.using.return_value.filter.return_value.order_by.return_value.values.return_value.__getitem__.return_value = []
            accounts = portal._paid_learner_accounts(29)
            self.assertEqual(accounts, [])
            manager.using.assert_called_once_with(portal.MOJPROP_DB_ALIAS)
            fields = manager.using.return_value.filter.call_args.kwargs
            self.assertEqual(fields["identity_id"], 29)
            self.assertEqual(fields["invoice_owner__identity_id"], 29)
            self.assertIs(fields["invoice_owner__settlement_verified"], True)
            self.assertEqual(fields["invoice_owner__payment__product"], portal.PRODUCT)
            self.assertEqual(
                fields["invoice_owner__payment__status"],
                portal.PropSimulationPayment.Status.PAID,
            )

    def test_invalid_identity_number_cannot_query_paid_account(self):
        for invalid in (0, -1, True, "29", None):
            with self.subTest(identity=invalid):
                with patch.object(portal.PropSimulationAccount, "objects") as manager:
                    self.assertEqual(portal._paid_learner_accounts(invalid), [])
                    manager.assert_not_called()

    def test_tampered_stored_journal_is_not_displayed(self):
        case = "MPS30-" + "B" * 20
        request = RequestFactory().get("/mojprop-buyer-portal/", {"case": case})
        request.session = {portal._SESSION_ID: 29}
        event = SimpleNamespace(
            payload={
                "schema": "mojprop.starter30.buyer_education.v1",
                "sessions": [{"session": 1, "closing_equity_usd": "1000.00",
                              "risk_plan_recorded": True, "reflection_recorded": True}],
                "verified_trade_evidence": False,
                "payout_eligibility": False,
            },
            payload_digest="0" * 64,
        )
        with patch.object(portal.PropSimulationEvent, "objects") as manager:
            manager.using.return_value.select_related.return_value.get.return_value = event
            with self.assertRaises(Http404):
                portal._report(request, case)
            claimed = manager.using.return_value.select_related.return_value.get.call_args.kwargs
            self.assertEqual(claimed["account__identity_id"], 29)
            self.assertEqual(claimed["account__invoice_owner__identity_id"], 29)
            self.assertEqual(claimed["account__invoice_owner__payment__product"], portal.PRODUCT)
            self.assertEqual(
                claimed["account__invoice_owner__payment__status"],
                portal.PropSimulationPayment.Status.PAID,
            )

    def test_unknown_email_never_sends_code_or_creates_entitlement(self):
        request = RequestFactory().post(
            "/mojprop-buyer-portal/",
            {"action": "request", "email": "unknown@example.invalid"},
        )
        request.session = {}
        with patch.object(portal, "_identity_keys", return_value=("s" * 64, "e" * 64)):
            with patch.object(portal.PropSimulationIdentity, "objects") as manager:
                manager.using.return_value.filter.return_value.first.return_value = None
                with patch.object(portal, "send_mail") as mail:
                    with patch.object(portal.PropSimulationLoginChallenge, "objects") as challenges:
                        result = portal._request_code(request)
                        self.assertEqual(result.status_code, 200)
                        self.assertIn(b"If a verified Starter30 account exists", result.content)
                        self.assertNotIn(portal._SESSION_ID, request.session)
                        mail.assert_not_called()
                        challenges.assert_not_called()

    def test_route_and_settings_require_all_explicit_optins(self):
        settings = SETTINGS.read_text(encoding="utf8")
        urls = URLS.read_text(encoding="utf8")
        source = APP.read_text(encoding="utf8")
        for key in GATES:
            if key in ("SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE"):
                continue
            self.assertIn(key, settings)
            self.assertIn(key, urls)
            self.assertIn(key, source)
        self.assertIn("path(\"mojprop-buyer-portal/\", buyer_portal", urls)
        self.assertIn("default=False", settings)
        for banned in (
            "issue_invoice(", "settle_invoice(", "commit_full_profit_payout(",
            "query_solidified_transfer(", "send_trx(", "real_order(",
        ):
            self.assertNotIn(banned, source)
        self.assertIn("invoice_owner__settlement_verified=True", source)
        self.assertIn("invoice_owner__payment__product=PRODUCT", source)
        self.assertIn("invoice_owner__payment__status=PropSimulationPayment.Status.PAID", source)
        self.assertIn("account.kind != PropSimulationAccount.Kind.CHALLENGE", source)
        self.assertIn("payout_eligibility", source)


if __name__ == "__main__":
    import unittest
    unittest.main()
