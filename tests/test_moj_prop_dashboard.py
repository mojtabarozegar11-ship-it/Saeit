"""Moj Prop private account portal integration and authorization checks."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from prop_firm.models import (
    PropAccount, PropTrader, PropExecution, PropEquityObservation,
)
from prop_firm.portal import account_projection
from prop_firm.portal_i18n import labels_for
from prop_firm.moj_prop_page import SUPPORTED_CODES


HOSTS = ["mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"]
SOURCE_DATE = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


@override_settings(ALLOWED_HOSTS=HOSTS)
class MojPropDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username="prop_owner", password="Passw0rd-Sample")
        cls.stranger = User.objects.create_user(username="prop_stranger", password="Passw0rd-Sample")
        cls.profile = PropTrader.objects.create(user=cls.owner)
        cls.other_profile = PropTrader.objects.create(user=cls.stranger)
        cls.account = PropAccount.objects.create(
            trader=cls.profile, kind=PropAccount.Kind.PHASE_ONE,
            starting_capital_usd=Decimal("100.00"),
        )
        cls.foreign_account = PropAccount.objects.create(
            trader=cls.other_profile, kind=PropAccount.Kind.PHASE_ONE,
        )

    def request_dashboard(self, url="/moj-prop/dashboard/", host="mojplaywin.com"):
        return self.client.get(url, HTTP_HOST=host)

    def test_unauthenticated_session_never_sees_accounts(self):
        response = self.request_dashboard()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/moj-prop/")
        self.assertIn("no-store", response["Cache-Control"])

    def test_authenticated_owner_view_is_private(self):
        self.client.force_login(self.owner)
        response = self.request_dashboard()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trader dashboard")
        self.assertContains(response, 'lang="en"')
        self.assertIn("private, no-store", response["Cache-Control"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertContains(response, "Trading and transfers are disabled")

    def test_object_isolation_and_no_foreign_trade_leak(self):
        PropExecution.objects.create(
            account=self.foreign_account, external_event_id="other-trade-1",
            data_source="test-verification", symbol="SECRET_OTHERS_SYMBOL",
            closed_at=SOURCE_DATE, gross_realized_usd=25,
            total_fees_usd=1, reconciliation_status="verified",
        )
        self.client.force_login(self.owner)
        response = self.request_dashboard()
        self.assertNotContains(response, "SECRET_OTHERS_SYMBOL")
        self.assertEqual(len(response.context["records"]), 1)
        self.assertEqual(response.context["records"][0]["account"].pk, self.account.pk)

    def test_farsi_and_rtl_dashboard(self):
        self.client.force_login(self.owner)
        response = self.request_dashboard("/moj-prop/fa/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lang="fa" dir="rtl"')
        self.assertContains(response, "داشبورد معامله‌گر")
        self.assertContains(response, "mojtaba.bot.ai")

    def test_all_20_localized_dashboards(self):
        self.client.force_login(self.owner)
        for code in SUPPORTED_CODES:
            url = "/moj-prop/dashboard/" if code == "en" else f"/moj-prop/{code}/dashboard/"
            with self.subTest(locale=code):
                response = self.request_dashboard(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, labels_for(code)[0])

    def test_host_and_unknown_language_rejected(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.request_dashboard(host="zomorodmelal.ir").status_code, 404)
        self.assertEqual(self.request_dashboard("/moj-prop/xx/dashboard/").status_code, 404)

    def test_customer_cannot_post_broker_metrics(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            "/moj-prop/dashboard/",
            data={"profit": "999999", "status": "passed"}, HTTP_HOST="mojplaywin.com",
        )
        self.assertEqual(response.status_code, 405)
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, PropAccount.Status.WAITING)

    def test_without_profile_no_auto_created_accounts(self):
        extra = get_user_model().objects.create_user(username="no_profile", password="Passw0rd-Sample")
        self.client.force_login(extra)
        response = self.request_dashboard()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No linked trading account yet")
        self.assertEqual(PropTrader.objects.filter(user=extra).count(), 0)

    def test_unverified_trade_hidden_and_cannot_pass(self):
        PropExecution.objects.create(
            account=self.account, external_event_id="pending-1", data_source="manual",
            symbol="NOT_VERIFIED", closed_at=SOURCE_DATE, gross_realized_usd=100,
            total_fees_usd=0, reconciliation_status="pending",
        )
        result = account_projection(self.account)
        self.assertEqual(result["net_profit"], 0)
        self.assertFalse(result["verified"])
        self.assertIsNone(result["assessment"])
        self.client.force_login(self.owner)
        self.assertNotContains(self.request_dashboard(), "NOT_VERIFIED")

    def test_verified_account_balance_is_read_only_projection(self):
        PropExecution.objects.create(
            account=self.account, external_event_id="reconciled-1", data_source="verified-adapter",
            symbol="EURUSD", closed_at=SOURCE_DATE, gross_realized_usd=8,
            total_fees_usd=Decimal("0.50"), reconciliation_status="verified",
            evidence_digest="a" * 64,
        )
        PropEquityObservation.objects.create(
            account=self.account, external_event_id="open", observed_at=SOURCE_DATE,
            is_session_open=True, equity_usd=100, reconciliation_status="verified",
        )
        PropEquityObservation.objects.create(
            account=self.account, external_event_id="mark",
            observed_at=datetime(2026,11,14,13,0,tzinfo=timezone.utc),
            is_session_open=False, equity_usd=107.5, reconciliation_status="verified",
        )
        self.account.reconciled_by_operator = True
        self.account.save(update_fields=["reconciled_by_operator"])
        result = account_projection(self.account)
        self.assertEqual(result["net_profit"], Decimal("7.50"))
        self.assertEqual(result["trading_days"], 1)
        self.assertEqual(result["best_day"], Decimal("7.50"))
        self.assertIsNotNone(result["assessment"])
        self.assertFalse(result["assessment"].passed)  # only one day, not six
        self.client.force_login(self.owner)
        self.assertContains(self.request_dashboard(), "EURUSD")

    def test_funded_tier_cannot_misstate_cash_amount(self):
        bad = PropAccount(
            trader=self.profile, kind=PropAccount.Kind.FUNDED,
            tier_index=10, starting_capital_usd=Decimal("5000"), reference="broker-1",
        )
        with self.assertRaises(ValidationError):
            bad.full_clean()
        valid = PropAccount(
            trader=self.profile, kind=PropAccount.Kind.FUNDED,
            tier_index=10, starting_capital_usd=Decimal("50000"), reference="broker-1",
        )
        valid.full_clean()

    def test_raw_customer_accounts_cannot_be_created_from_dashboard(self):
        self.client.force_login(self.owner)
        before = PropAccount.objects.count()
        self.request_dashboard()
        self.assertEqual(PropAccount.objects.count(), before)

    def test_historical_daily_breach_cannot_be_hidden_by_recovery(self):
        PropExecution.objects.create(
            account=self.account, external_event_id="historical-trade",
            data_source="verified-adapter", symbol="GBPUSD",
            closed_at=SOURCE_DATE, gross_realized_usd=Decimal("10"),
            reconciliation_status="verified",
        )
        PropEquityObservation.objects.create(
            account=self.account, external_event_id="start",
            observed_at=datetime(2026, 11, 14, 9, 0, tzinfo=timezone.utc),
            is_session_open=True, equity_usd=100, reconciliation_status="verified",
        )
        PropEquityObservation.objects.create(
            account=self.account, external_event_id="breach",
            observed_at=datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc),
            equity_usd=96, reconciliation_status="verified",
        )
        PropEquityObservation.objects.create(
            account=self.account, external_event_id="recovery",
            observed_at=datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc),
            equity_usd=110, reconciliation_status="verified",
        )
        self.account.reconciled_by_operator = True
        self.account.save(update_fields=["reconciled_by_operator"])
        result = account_projection(self.account)
        self.assertFalse(result["verified"])
        self.assertFalse(result["risk"].allowed)
        self.assertIn("daily_loss_floor_reached", result["risk"].reasons)
        self.assertFalse(result["assessment"].passed)

    def test_incomplete_equity_and_unverified_execution_block_qualification(self):
        PropExecution.objects.create(
            account=self.account, external_event_id="verified-one",
            data_source="verified-adapter", symbol="USDJPY",
            closed_at=SOURCE_DATE, gross_realized_usd=Decimal("10"),
            reconciliation_status="verified",
        )
        PropExecution.objects.create(
            account=self.account, external_event_id="in-review",
            data_source="verified-adapter", symbol="AUDUSD",
            closed_at=SOURCE_DATE, gross_realized_usd=Decimal("100"),
            reconciliation_status="pending",
        )
        PropEquityObservation.objects.create(
            account=self.account, external_event_id="open-day",
            observed_at=SOURCE_DATE, equity_usd=100, is_session_open=True,
            reconciliation_status="verified",
        )
        self.account.reconciled_by_operator = True
        self.account.save(update_fields=["reconciled_by_operator"])
        result = account_projection(self.account)
        self.assertFalse(result["verified"])
        self.assertEqual(result["net_profit"], Decimal("10"))
        self.assertFalse(result["assessment"].passed)

    def test_duplicate_daily_open_is_not_a_clean_reconciliation(self):
        PropExecution.objects.create(
            account=self.account, external_event_id="valid-trade",
            data_source="verified-adapter", symbol="EURUSD",
            closed_at=SOURCE_DATE, gross_realized_usd=1,
            reconciliation_status="verified",
        )
        for event_id, hour in (("first_open", 8), ("second_open", 9)):
            PropEquityObservation.objects.create(
                account=self.account, external_event_id=event_id,
                observed_at=datetime(2026, 11, 14, hour, tzinfo=timezone.utc),
                equity_usd=100, is_session_open=True,
                reconciliation_status="verified",
            )
        self.account.reconciled_by_operator = True
        self.account.save(update_fields=["reconciled_by_operator"])
        result = account_projection(self.account)
        self.assertFalse(result["verified"])
        self.assertIn("duplicate_session_open", result["risk"].reasons)
