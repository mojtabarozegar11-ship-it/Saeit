"""Single, verified Mojtaba.bot.ai brand referral — not a paid signal sale."""
from django.test import SimpleTestCase, override_settings

from core.financial_brand_pages import BRANDS, SOLE_BOT_PUBLIC_URL


@override_settings(
    ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com",
                   "zomorodmelal.ir", "www.zomorodmelal.ir",
                   "evilzomorodmelal.ir.attacker.example"],
    USE_X_FORWARDED_HOST=False,
)
class SingleBotBrandReferralTests(SimpleTestCase):
    def get_page(self, brand="saman", section="market-signals", *,
                 host="mojplaywin.com", language=None, forwarded=None):
        path = f"/{brand}/{section}/"
        if language == "ar":
            path = "/ar" + path
        kwargs = {"HTTP_HOST": host}
        if forwarded:
            kwargs["HTTP_X_FORWARDED_HOST"] = forwarded
        return self.client.get(path, **kwargs)

    def test_public_bot_referral_off_by_default(self):
        with override_settings(MOJTABA_BOT_PUBLIC_VERIFIED=False):
            response = self.get_page()
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'href="https://mojtaba.bot.ai/"')

    def test_string_truthy_flag_not_accepted(self):
        with override_settings(MOJTABA_BOT_PUBLIC_VERIFIED="true"):
            self.assertNotContains(self.get_page(), 'href="https://mojtaba.bot.ai/"')

    def test_all_17_brands_handoff_to_exactly_one_bot(self):
        with override_settings(MOJTABA_BOT_PUBLIC_VERIFIED=True):
            self.assertEqual(len(BRANDS), 17)
            for brand, *_ in BRANDS:
                with self.subTest(brand=brand):
                    page = self.get_page(brand=brand)
                    self.assertEqual(page.status_code, 200)
                    self.assertContains(page, f'href="{SOLE_BOT_PUBLIC_URL}"', count=1)

    def test_localized_persian_referral_without_financial_promises(self):
        with override_settings(MOJTABA_BOT_PUBLIC_VERIFIED=True):
            response = self.get_page(host="zomorodmelal.ir")
            self.assertContains(response, 'lang="fa"')
            self.assertContains(response, "خدمات پژوهشی")
            self.assertNotContains(response, "سود تضمینی")

    def test_localized_english_referral(self):
        with override_settings(MOJTABA_BOT_PUBLIC_VERIFIED=True):
            response = self.get_page()
            self.assertContains(response, 'lang="en"')
            self.assertContains(response, "non-financial research")

    def test_localized_arabic_referral(self):
        with override_settings(MOJTABA_BOT_PUBLIC_VERIFIED=True):
            response = self.get_page(language="ar")
            self.assertContains(response, 'lang="ar"')
            self.assertContains(response, "خدمات البحث")

    def test_no_bot_link_on_store_pages(self):
        with override_settings(MOJTABA_BOT_PUBLIC_VERIFIED=True):
            for brand, *_ in BRANDS:
                with self.subTest(brand=brand):
                    self.assertNotContains(
                        self.get_page(brand=brand, section="digital-products"),
                        f'href="{SOLE_BOT_PUBLIC_URL}"',
                    )

    def test_no_bot_link_on_game_pages(self):
        with override_settings(MOJTABA_BOT_PUBLIC_VERIFIED=True):
            self.assertNotContains(
                self.get_page(section="game"),
                f'href="{SOLE_BOT_PUBLIC_URL}"',
            )

    def test_forwarded_attacker_host_cannot_switch_language(self):
        with override_settings(MOJTABA_BOT_PUBLIC_VERIFIED=True):
            response = self.get_page(
                host="mojplaywin.com",
                forwarded="www.zomorodmelal.ir.evil.example",
            )
            self.assertContains(response, 'lang="en"')

    def test_substring_host_spoof_does_not_get_persian_locale(self):
        with override_settings(MOJTABA_BOT_PUBLIC_VERIFIED=True):
            response = self.get_page(
                host="evilzomorodmelal.ir.attacker.example")
            self.assertContains(response, 'lang="en"')

    def test_bot_flag_does_not_create_checkout_form(self):
        with override_settings(MOJTABA_BOT_PUBLIC_VERIFIED=True):
            response = self.get_page()
            self.assertNotContains(response, 'name="wallet_address"')
            self.assertNotContains(response, 'name="tx_id"')
            self.assertContains(response, "No checkout, paid access")

    def test_single_bot_reference_is_https_root_not_unverified_sales_path(self):
        self.assertEqual(SOLE_BOT_PUBLIC_URL, "https://mojtaba.bot.ai/")

    def test_no_unregistered_brand_route(self):
        self.assertEqual(self.get_page(brand="nobody").status_code, 404)
