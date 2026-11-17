"""Signal catalog coverage across 17 established branded market-analysis pages."""
from datetime import datetime, timezone
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.signal_commercial_catalog import (
    SIGNAL_BRANDS, SUPPORTED_LOCALES, CANONICAL_AGENT,
    offer, catalog, inspect_signal_record,
)
from core.financial_brand_pages import BRANDS


class SignalsPolicyTests(SimpleTestCase):
    def valid_record(self, **updates):
        record = {
            "event_id": "broker:20261114:123", "symbol": "XAUUSD",
            "side": "buy", "created_at": datetime(2026,11,14,tzinfo=timezone.utc),
            "entry": "4000", "stop_loss": "3980", "take_profit": "4040",
            "verified_source": True,
        }
        record.update(updates)
        return record

    def test_all_known_brand_slugs_mapped(self):
        self.assertEqual(SIGNAL_BRANDS, tuple(row[0] for row in BRANDS))
        self.assertEqual(len(SIGNAL_BRANDS), 17)

    def test_three_locales_for_each_brand(self):
        result = catalog()
        self.assertEqual(len(result), 51)
        self.assertEqual(len(set((r.brand, r.locale) for r in result)), 51)

    def test_only_one_automation_identity(self):
        self.assertEqual(CANONICAL_AGENT, "mojtaba.bot.ai")
        self.assertTrue(all(x.agent_identity == CANONICAL_AGENT for x in catalog()))

    def test_no_fake_prices_or_paid_subscriptions(self):
        for row in catalog():
            self.assertIsNone(row.price_usd)
            self.assertFalse(row.checkout_enabled)
            self.assertFalse(row.signal_history_verified)
            self.assertFalse(row.performance_metrics_available)

    def test_unknown_brand_rejected(self):
        with self.assertRaises(ValueError):
            offer("not_a_real_brand", "en")

    def test_unknown_locale_rejected(self):
        with self.assertRaises(ValueError):
            offer("saman", "xx")

    def test_arabic_route_stays_distinct(self):
        self.assertEqual(offer("saman", "ar").landing_path, "/ar/saman/market-signals/")
        self.assertEqual(offer("saman", "en").landing_path, "/saman/market-signals/")

    def test_complete_syntactic_record_is_not_paid_entitlement(self):
        self.assertTrue(inspect_signal_record(self.valid_record()))
        self.assertFalse(offer("saman","en").checkout_enabled)

    def test_unverified_provider_cannot_claim_signal(self):
        self.assertFalse(inspect_signal_record(self.valid_record(verified_source=False)))

    def test_false_signals_require_target_below_entry_below_stop(self):
        self.assertTrue(inspect_signal_record(self.valid_record(
            side="sell", take_profit="3975", stop_loss="4010")))
        self.assertFalse(inspect_signal_record(self.valid_record(
            side="sell", take_profit="4020", stop_loss="3990")))

    def test_invalid_buy_stop_or_takeprofit_rejected(self):
        self.assertFalse(inspect_signal_record(self.valid_record(stop_loss="4100")))
        self.assertFalse(inspect_signal_record(self.valid_record(take_profit="3900")))

    def test_buyer_supplied_float_prices_rejected(self):
        self.assertFalse(inspect_signal_record(self.valid_record(entry=4000.0)))

    def test_exponential_and_extreme_signal_prices_rejected_globally(self):
        for price in ("1e10000000", "0."+"1"*20000, "1"*19, "۱۲۳",
                      "+1.0", "1.000000001"):
            with self.subTest(length=len(price)):
                self.assertFalse(inspect_signal_record(
                    self.valid_record(entry=price),
                ))

    def test_bounded_eight_decimal_signal_prices_supported(self):
        self.assertTrue(inspect_signal_record(self.valid_record(
            entry="0.00000120", stop_loss="0.00000119",
            take_profit="0.00000121",
        )))

    def test_nonfinite_prices_rejected(self):
        self.assertFalse(inspect_signal_record(self.valid_record(entry="NaN")))
        self.assertFalse(inspect_signal_record(self.valid_record(entry="Infinity")))

    def test_utc_only_timestamp(self):
        self.assertFalse(inspect_signal_record(self.valid_record(
            created_at=datetime(2026, 11, 14))))
        self.assertFalse(inspect_signal_record(self.valid_record(
            created_at="2026-11-14T00:00:00Z")))

    def test_bad_event_id_disallowed(self):
        self.assertFalse(inspect_signal_record(self.valid_record(event_id="../escape")))

    def test_more_properties_are_rejected(self):
        x = self.valid_record()
        x["guaranteed_return"] = "100%"
        self.assertFalse(inspect_signal_record(x))


@override_settings(ALLOWED_HOSTS=["mojplaywin.com","zomorodmelal.ir","testserver"])
class SignalsBrandRouteTests(TestCase):
    def test_all_seventeen_english_landing_pages_render(self):
        for slug in SIGNAL_BRANDS:
            with self.subTest(slug=slug):
                response = self.client.get(f"/{slug}/market-signals/", HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Signal subscriptions are not for sale yet.")
                self.assertContains(response, "MOJTABA.BOT.AI")

    def test_all_seventeen_arabic_landing_pages_render(self):
        for slug in SIGNAL_BRANDS:
            with self.subTest(slug=slug):
                response = self.client.get(f"/ar/{slug}/market-signals/", HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "الاشتراك في إشارات السوق غير متاح للبيع بعد")

    def test_persian_site_uses_persian_offer_disclosure(self):
        response = self.client.get("/saman/market-signals/", HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "اشتراک سیگنال هنوز برای فروش فعال نیست.")

    def test_no_subscriptions_or_payment_cta_on_signal_page(self):
        response = self.client.get("/saman/market-signals/", HTTP_HOST="mojplaywin.com")
        html = response.content.decode("utf-8").lower()
        self.assertIn('data-signal-subscription="not-released"', html)
        self.assertNotIn('<form', html)
        self.assertNotIn("guaranteed profit", html)
        self.assertNotIn("/signal/checkout/", html)
