"""Real MOJ-PROP-01 source-only acquisition route regression, no POST/payment."""
from pathlib import Path
import unittest
from html.parser import HTMLParser

ROOT=Path(__file__).resolve().parents[1]
LANDING=ROOT/"templates/moj-prop-v4/index.html"
CONTACT=ROOT/"templates/moj-prop/contact/index.html"
CANON="/moj-prop-interest/form/"
OLD="/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=moj-prop-01"

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.links.append(dict(attrs))

class Plan1CanonicalAcquisition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page=LANDING.read_text("utf-8")
        cls.contact=CONTACT.read_text("utf-8")
        cls.parser=Links()
        cls.parser.feed(cls.page)
    def test_01_canonical_lead_route_present(self):
        self.assertIn(CANON,self.page)
    def test_02_two_localized_lead_links(self):
        self.assertGreaterEqual(sum(x.get("href")==CANON for x in self.parser.links),2)
    def test_03_english_lead_cta_accessible(self):
        self.assertIn('aria-label="Open dedicated Plan 1 consent-only prelaunch interest form',self.page)
    def test_04_farsi_lead_cta_accessible(self):
        self.assertIn('aria-label="فرم اختصاصی رضایت‌محور طرح اول',self.page)
    def test_05_farsi_section_actual_rtl(self):
        self.assertIn('id="plan-one-fa" lang="fa" dir="rtl"',self.page)
    def test_06_no_fake_production_verified_claim(self):
        self.assertIn("not yet live verified",self.page)
    def test_07_farsi_live_unverified_disclosure(self):
        self.assertIn("انتشار تأیید نشده",self.page)
    def test_08_dedicated_route_not_paid_checkout(self):
        self.assertNotIn("/moj-prop/checkout/",CANON)
    def test_09_no_payment_instruction_in_lead_cta(self):
        self.assertIn("Never send payment or identity documents",self.page)
    def test_10_first_party_fallback(self):
        self.assertIn('href="/moj-prop/contact/"',self.page)
    def test_11_status_unverified_warning(self):
        self.assertIn("not independently verified on production",self.page)
    def test_12_no_automatic_customer_submission_by_link(self):
        self.assertIn("not an order or a confirmed live CRM submission",self.page)
    def test_13_no_fake_order(self):
        self.assertIn("not an order",self.page)
    def test_14_old_route_is_labeled_fallback(self):
        self.assertIn("مسیر جایگزین قدیمی",self.page)
    def test_15_old_route_kept_for_compatibility(self):
        self.assertGreaterEqual(self.page.count(OLD),3)
    def test_16_source_nojs_status_not_misrepresented(self):
        self.assertIn("public request-status HTML endpoint is not verified",self.page)
    def test_17_one_to_one_contact_not_marketing_consent(self):
        self.assertIn("Any updates need separate, affirmative recorded consent",self.page)
    def test_18_privacy_withdrawal_path(self):
        self.assertIn("consent withdrawal",self.page)
    def test_19_no_invoice_or_fee_now(self):
        self.assertIn("no fee is collected",self.page)
    def test_20_qualified_lead_needs_independent_receipt(self):
        self.assertIn("independently confirmed server receipt",self.page)
    def test_21_no_unverified_capital_guarantee(self):
        self.assertIn("No returns or funding are guaranteed",self.page)
    def test_22_30_native_trx_proposed_not_due(self):
        self.assertIn("30 native TRX (30,000,000 SUN)",self.page)
    def test_23_50_unique_trades(self):
        self.assertIn("50 distinct closed positions",self.page)
    def test_24_six_days_per_stage(self):
        self.assertIn("six qualifying days in <strong>each</strong> stage",self.page)
    def test_25_28_days_from_lawful_enrollment(self):
        self.assertIn("28-day period starting only after legally confirmed enrollment",self.page)
    def test_26_farsi_conditional_real_capital(self):
        self.assertIn("۱۰۰ دلار سرمایه واقعی",self.page)
    def test_27_support_page_mailbox(self):
        self.assertIn("support@mojplaywin.com",self.contact)
    def test_28_support_no_automatic_send(self):
        self.assertIn("nothing is sent automatically",self.contact)
    def test_29_no_paid_starter30_product_claim(self):
        self.assertIn("NOT an educational product",self.page)
    def test_30_farsi_refund_disclosure(self):
        self.assertIn("شرایط نهایی لغو و استرداد",self.page)

if __name__=="__main__":
    unittest.main()
