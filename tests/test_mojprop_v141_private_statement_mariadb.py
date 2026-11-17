"""Real Django request+MariaDB tests for a disabled-by-default private statement.

Runs only with the disposable loopback MariaDB CI settings; never connects to
site production. The tests do not provide or validate external market data.
"""
from datetime import timedelta
from decimal import Decimal
import hashlib
import hmac

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.test import RequestFactory, TransactionTestCase, override_settings
from django.utils import timezone

from core.mojprop_v141_private_statement_view import moj_prop_v141_private_statement
from prop_firm.plan1_v14_social_or_50_terms import review_prospective_terms
from prop_firm.plan1_v141_persistence_models import PropV141SimState
from prop_firm.plan1_v141_virtual_tenant_models import PropV141VirtualBook, PropV141VirtualFill
from prop_firm.plan1_v141_virtual_tenant_fill_ledger import VirtualFill
from prop_firm.plan1_v141_atomic_virtual_fill_service import _payload, store_v141_virtual_fill

CHALLENGE = "CHALLENGE-CI-PRIVATE-STATEMENT-AAA"
KEY = b"C" * 32
KEY_ID = "ci-statement-key"
FEED = "ci-private-feed"
SOURCE_HASH = "a" * 64


@override_settings(
    MOJ_PROP_V141_PORTFOLIO_ENABLED=True,
    ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com"],
)
class PrivateStatementMariaDBTests(TransactionTestCase):
    databases = {"default"}

    def setUp(self):
        self.factory = RequestFactory()
        self.now = timezone.now()
        self.start = self.now - timedelta(days=1)
        self.owner = get_user_model().objects.create_user(username="ci-private-owner")
        self.other = get_user_model().objects.create_user(username="ci-private-other")
        self.state = PropV141SimState.objects.create(
            challenge_ref=CHALLENGE,
            terms_sha256=review_prospective_terms().contract_candidate_sha256,
            trusted_source="ci-publisher",
            trusted_key_id=KEY_ID,
            trusted_feed_source=FEED,
        )
        self.book = PropV141VirtualBook.objects.create(
            state=self.state, owner=self.owner, trader_ref="TRADER-CI-PRIVATE",
            terms_sha256=self.state.terms_sha256,
            trusted_feed_source=FEED, evaluation_started_at=self.start,
        )

    def _request(self, *, user=None, host="mojplaywin.com", secure=True,
                 method="GET", query="", lang="en", ref=CHALLENGE):
        uri = f"/moj-prop-v141/statement/{ref}/"
        if query:
            uri += "?" + query
        request = self.factory.generic(method, uri, secure=secure,
                                       HTTP_HOST=host,
                                       HTTP_ACCEPT_LANGUAGE=lang)
        request.user = user if user is not None else self.owner
        return request

    def _call(self, **kwargs):
        req = self._request(**kwargs)
        ref = kwargs.get("ref", CHALLENGE)
        return moj_prop_v141_private_statement(req, ref)

    def _raw_fill(self, seq):
        return PropV141VirtualFill.objects.create(
            book=self.book, sequence=seq, event_id=f"CI-VIEW-EVENT-{seq}",
            position_ref=f"CI-VIEW-POS-{seq}", stage=1,
            action="OPEN", direction="BUY", symbol="XAUUSD",
            quantity_ounces=Decimal("0.0100"),
            price_usd_per_ounce=Decimal("3000.0000"),
            fee_usd=Decimal("0.0000"),
            executed_at_utc=self.start + timedelta(minutes=seq),
            feed_source=FEED, raw_event_sha256=SOURCE_HASH,
        )

    def test_01_actual_database_owner_sees_own_statement(self):
        result = self._call()
        self.assertEqual(result.status_code, 200)
        self.assertIn(CHALLENGE, result.content.decode("utf-8"))
        self.assertIn("DEMO RECORDS ONLY", result.content.decode("utf-8"))

    def test_02_anonymous_user_redirects_to_login_not_private_content(self):
        result = self._call(user=AnonymousUser())
        self.assertEqual(result.status_code, 302)
        self.assertIn("/admin/login/", result["Location"])
        self.assertNotIn(CHALLENGE, result.content.decode("utf-8"))

    def test_03_other_real_site_user_cannot_read_first_users_book(self):
        with self.assertRaises(Http404):
            self._call(user=self.other)

    def test_04_unknown_challenge_denied_without_owner_disclosure(self):
        with self.assertRaises(Http404):
            self._call(ref="CHALLENGE-CI-UNKNOWN")

    def test_05_disabled_flag_always_blocks_owner_even_with_db_rows(self):
        with override_settings(MOJ_PROP_V141_PORTFOLIO_ENABLED=False):
            with self.assertRaises(Http404):
                self._call()

    def test_06_no_flag_also_blocks_if_not_explicitly_true(self):
        with override_settings(MOJ_PROP_V141_PORTFOLIO_ENABLED="true"):
            with self.assertRaises(Http404):
                self._call()

    def test_07_only_https_mojplaywin_host(self):
        with self.assertRaises(Http404):
            self._call(secure=False)
        with self.assertRaises(Http404):
            self._call(host="another-website.com")

    def test_08_www_alias_is_scoped_and_permitted(self):
        self.assertEqual(self._call(host="www.mojplaywin.com").status_code, 200)

    def test_09_query_strings_denied(self):
        with self.assertRaises(Http404):
            self._call(query="show=all")

    def test_10_invalid_or_long_slug_denied(self):
        with self.assertRaises(Http404):
            self._call(ref="A" * 100)
        with self.assertRaises(Http404):
            self._call(ref="DOT.FORBIDDEN")

    def test_11_post_and_put_cannot_write_any_fills(self):
        for method in ("POST", "PUT"):
            result = self._call(method=method)
            self.assertEqual(result.status_code, 405)
        self.assertEqual(PropV141VirtualFill.objects.count(), 0)

    def test_12_security_headers_deny_cache_embedding_index_and_forms(self):
        result = self._call()
        self.assertIn("no-store", result["Cache-Control"])
        self.assertEqual(result["X-Frame-Options"], "DENY")
        self.assertIn("noindex", result["X-Robots-Tag"])
        self.assertIn("form-action 'none'", result["Content-Security-Policy"])
        self.assertEqual(result["Referrer-Policy"], "no-referrer")

    def test_13_fa_locale_rtl_while_en_locale_ltr(self):
        fa = self._call(lang="fa-IR,fa;q=0.9").content.decode("utf-8")
        en = self._call(lang="en-US,en;q=0.9").content.decode("utf-8")
        self.assertIn('lang="fa" dir="rtl"', fa)
        self.assertIn("صورتحساب خصوصی", fa)
        self.assertIn('lang="en" dir="ltr"', en)
        self.assertIn("Private virtual statement", en)

    def test_14_exact_shared_28_day_deadline_not_56_days(self):
        html = self._call().content.decode("utf-8")
        target = (self.start + timedelta(days=28)).strftime("%Y-%m-%d %H:%M:%S")
        self.assertIn(target, html)
        self.assertIn("overall 28-day window", html)

    def test_15_recent_fills_bounded_to_25_database_rows(self):
        PropV141VirtualFill.objects.bulk_create([
            PropV141VirtualFill(
                book=self.book, sequence=i, event_id=f"CI-SEQ-{i}",
                position_ref=f"P-{i}", stage=1, action="OPEN",
                direction="BUY", symbol="XAUUSD",
                quantity_ounces=Decimal("0.0100"),
                price_usd_per_ounce=Decimal("3000.0000"),
                fee_usd=Decimal("0.0000"),
                executed_at_utc=self.start + timedelta(minutes=i),
                feed_source=FEED, raw_event_sha256=SOURCE_HASH,
            ) for i in range(1, 31)
        ])
        html = self._call().content.decode("utf-8")
        self.assertEqual(html.count("<tr>"), 26)  # 25 records and one header
        self.assertIn("CI", CHALLENGE)
        self.assertNotIn("<script", html.lower())

    def test_16_browser_never_displays_broker_wallet_or_hmac_secret(self):
        html = self._call().content.decode("utf-8")
        for forbidden in ("ci-statement-key", KEY.decode("ascii"), "broker_password",
                          "wallet_private_key", "<form", "<script", "checkout"):
            self.assertNotIn(forbidden, html)

    def test_17_signed_writer_commit_is_reflected_in_private_html(self):
        event = VirtualFill(
            trader_ref=self.book.trader_ref,
            challenge_ref=CHALLENGE, event_id="CI-SIGNED-STATEMENT-FILL",
            sequence=1, position_ref="CI-SIGNED-POS", stage=1,
            action="OPEN", direction="BUY", symbol="XAUUSD",
            quantity_ounces="1.0000", price_usd_per_ounce="3000.0000",
            fee_usd="0.1000", executed_at_utc=self.start + timedelta(minutes=1),
            feed_source=FEED, raw_event_sha256=SOURCE_HASH,
        )
        sig = hmac.new(KEY, _payload(self.book,event), hashlib.sha256).hexdigest()
        stored = store_v141_virtual_fill(
            trusted_book_pk=self.book.pk,
            authenticated_site_user_pk=self.owner.pk,
            fill=event, ingress_signature_sha256=sig,
            server_owned_hmac_keys={KEY_ID:KEY}, server_now=self.now,
        )
        self.assertFalse(stored.idempotent_replay)
        html = self._call().content.decode("utf-8")
        self.assertIn("OPEN", html)
        self.assertIn("3000.0000", html)
        self.assertIn("0.10000000", html)
        self.assertEqual(PropV141VirtualFill.objects.count(), 1)

    def test_18_unauthorized_owner_cannot_discover_other_private_account_values(self):
        self.book.last_realized_net_usd = Decimal("-777.12345678")
        self.book.save(update_fields=["last_realized_net_usd"])
        with self.assertRaises(Http404):
            self._call(user=self.other)
        state2 = PropV141SimState.objects.create(
            challenge_ref="CHALLENGE-CI-PRIVATE-STATEMENT-BBB",
            terms_sha256=self.state.terms_sha256,
            trusted_source="ci-publisher", trusted_key_id=KEY_ID,
            trusted_feed_source=FEED,
        )
        PropV141VirtualBook.objects.create(
            state=state2, owner=self.other, trader_ref="TRADER-CI-OTHER",
            terms_sha256=self.state.terms_sha256,
            trusted_feed_source=FEED, evaluation_started_at=self.start,
            last_realized_net_usd=Decimal("12.34567890"),
        )
        own_html = self._call().content.decode("utf-8")
        self.assertIn("-777.12345678", own_html)
        self.assertNotIn("12.34567890", own_html)

    def test_19_empty_db_history_has_explicit_no_transactions_text(self):
        html = self._call().content.decode("utf-8")
        self.assertIn("No simulated fill events", html)

    def test_20_no_live_equity_or_paid_pass_claimed_in_private_statement(self):
        html = self._call().content.decode("utf-8")
        self.assertIn("not live market equity", html.lower())
        self.assertNotIn("Congratulations, you passed", html)
