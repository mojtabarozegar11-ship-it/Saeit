"""Static privacy and fail-closed source tests for virtual site account view.

These checks are NOT Django request tests. Real MariaDB, auth middleware,
permission boundaries and deployment remain unverified.
"""
from pathlib import Path
import ast
import unittest

ROOT=Path(__file__).resolve().parents[1]
VIEW=ROOT/"core/mojprop_v141_private_portfolio_view.py"
URLS=ROOT/"config/urls.py"


class PrivateVirtualPortfolioSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view=VIEW.read_text("utf-8")
        cls.urls=URLS.read_text("utf-8")

    def test_01_view_compiles(self):
        ast.parse(self.view)

    def test_02_urls_compile(self):
        ast.parse(self.urls)

    def test_03_route_does_not_replace_legacy_v12(self):
        self.assertIn('path("moj-prop-v141/portfolio/<slug:challenge_ref>/"',self.urls)
        self.assertIn('path("moj-prop-interest/form/"',self.urls)

    def test_04_disabled_without_explicit_setting_true(self):
        self.assertIn('getattr(settings, "MOJ_PROP_V141_PORTFOLIO_ENABLED", False) is not True',self.view)

    def test_05_authenticated_login_required(self):
        self.assertIn("@login_required",self.view)
        self.assertIn("request.user.pk",self.view)

    def test_06_query_filters_by_user_and_challenge(self):
        self.assertIn("owner_id=request.user.pk",self.view)
        self.assertIn("state__challenge_ref=challenge_ref",self.view)

    def test_07_second_ownership_check_before_output(self):
        self.assertIn("book.owner_id != request.user.pk",self.view)

    def test_08_no_matching_book_returns_not_found(self):
        self.assertIn('raise Http404("No matching private challenge")',self.view)

    def test_09_mojplaywin_https_required(self):
        self.assertIn('"mojplaywin.com"',self.view)
        self.assertIn('"www.mojplaywin.com"',self.view)
        self.assertIn("request.is_secure() is not True",self.view)

    def test_10_unsupported_methods_rejected(self):
        self.assertIn('request.method not in ("GET", "HEAD")',self.view)
        self.assertIn('HttpResponseNotAllowed(["GET", "HEAD"])',self.view)

    def test_11_query_params_blocked(self):
        self.assertIn('request.META.get("QUERY_STRING", "")',self.view)

    def test_12_no_cross_tenant_broker_credentials_in_json(self):
        self.assertNotIn("password",self.view.lower())
        self.assertNotIn("account_login",self.view)
        self.assertNotIn("trusted_signer_keys",self.view)
        self.assertNotIn("hmac_signature",self.view)

    def test_13_output_does_not_claim_unrealized_equity(self):
        self.assertIn("realized_only_no_floating_equity=True",self.view)
        self.assertIn("independently_reconciled_market_marks=False",self.view)

    def test_14_no_paid_enrollment_or_broker_orders_claimed(self):
        self.assertIn("paid_enrollment_active=False",self.view)
        self.assertIn("live_orders_enabled=False",self.view)

    def test_15_not_indexed(self):
        self.assertIn('"noindex, nofollow, noarchive"',self.view)

    def test_16_no_caching_other_users_balances(self):
        self.assertIn('"private, no-store, max-age=0"',self.view)

    def test_17_prevent_iframe_embedding(self):
        self.assertIn('response["X-Frame-Options"] = "DENY"',self.view)

    def test_18_no_mutating_orm_calls(self):
        for forbidden in ("objects.create(", "objects.update(", "objects.delete(",
                          ".save(", "transaction.atomic", "send_mail", "place_order"):
            self.assertNotIn(forbidden,self.view)

    def test_19_real_order_receipts_not_claimed(self):
        self.assertIn("company_broker_trade_receipt_verified=False",self.view)

    def test_20_no_payout_claimed(self):
        self.assertIn("payouts_enabled=False",self.view)


if __name__=="__main__":
    unittest.main()
