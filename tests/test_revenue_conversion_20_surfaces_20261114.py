"""No-network, no-purchase source-acceptance contracts for 20 revenue surfaces.

This does NOT prove live deployment, purchases, payments or delivered services.
"""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SURFACES = (
    ("R01", "content/zomorod-nova-pages/about.html", "شروع همکاری با شرح مسئله و مدارک", "/ask-master/index.php?service=1"),
    ("R02", "content/zomorod-nova-pages/company.html", "استعلام همکاری بین‌بخشی و زنجیرهٔ تأمین", "/ask-master/index.php?service=1"),
    ("R03", "content/zomorod-nova-pages/knowledge.html", "درخواست تولید محتوای علمی و آموزش تخصصی", "/ask-master/index.php?service=1"),
    ("R04", "content/zomorod-vision-v3/ar/index.html", "طلب تعاون مهني واضح", "/ask-master/index.php?service=1"),
    ("R05", "public/tala/index.html", "استعلام کارشناسی طلا، جواهر و گوهرسنگ", "/ask-master/index.php?service=1"),
    ("R06", "public/mohammad/index.html", "ساخت فایل محلی به معنی ثبت روی سرور", "/ask-master/index.php?service=1"),
    ("R07", "public/mohammad/guides/rooftop-solar-feasibility/index.html", "استعلام بررسی بام خورشیدی", "/ask-master/index.php?service=1"),
    ("R08", "public/mohammad/guides/summer-overheating-shading/index.html", "درخواست ارزیابی گرمایش تابستان", "/ask-master/index.php?service=1"),
    ("R09", "content/zomorod-it-products-20261019/index.html", "استعلام تحلیل اختصاصی خروجی ابزار", "/ask-master/index.php?service=1"),
    ("R10", "faremah/posters.html", "از مشاهده پوستر تا استعلام حرفه‌ای", "contact.html#form"),
    ("R11", "core/templates/core/services.html", "درخواست خدمات تخصصی؛ ابتدا دامنه کار را روشن کنیم", "/ask-master/index.php?service=1"),
    ("R12", "core/templates/core/auctions.html", "استعلام اطلاعات فرصت‌های آتی", "/ask-master/index.php?service=1"),
    ("R13", "core/templates/mojplaywin/store.html", "Before attempting a guest order, use your own valid email address", "/commerce/trx-easy/purchases/"),
    ("R14", "content/zomorod-nexus-20261112/index.html", "درخواست اولیه اطلاعات محرمانه یا پرداخت نفرستید", "/ask-master/index.php?service=1"),
    ("R15", "content/zomorod-new-home/index.html", "از مسئله واقعی تا پیشنهاد همکاری قابل ارزیابی", "/ask-master/index.php?service=1"),
    ("R16", "content/zomorod-p0-backlog/planting-planner/index.html", "استعلام برنامه کشت ویژهٔ گلخانه", "/ask-master/index.php?service=1"),
    ("R17", "farnaz/templates/farnaz/index.html", "Define the deliverable before commissioning CAD or 3D work", "#contact"),
    ("R18", "templates/studio_raha/index.html", "There is no active email subscription service on this page", "mailto:hello@mojplaywin.com"),
    ("R19", "templates/taniya_studio/index.html", "Check the storybook offer and delivery terms", "mailto:hello@mojplaywin.com"),
    ("R20", "templates/saman/index.html", "Choose an educational product by its evidence, not a return promise", "/saman/digital-products/"),
)


class RevenueConversionSourceTests(unittest.TestCase):
    def test_20_different_verified_source_files_have_relevant_next_steps(self):
        self.assertEqual(len(SURFACES), 20)
        self.assertEqual(len({path for _, path, _, _ in SURFACES}), 20)
        for marker, relative, scope, action in SURFACES:
            with self.subTest(surface=marker, path=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertEqual(text.count('data-revenue-surface="' + marker + '"'), 1)
                self.assertIn(scope, text)
                self.assertIn(action, text)
                self.assertGreater(len(text), 700)

    def test_static_html_surfaces_are_parseable(self):
        # HTMLParser is a syntax smoke check, not a full browser/Django test.
        for marker, relative, _, _ in SURFACES:
            with self.subTest(surface=marker):
                p = HTMLParser(convert_charrefs=True)
                p.feed((ROOT / relative).read_text(encoding="utf-8"))
                p.close()

    def test_studio_raha_no_fake_subscriber_capture(self):
        text = (ROOT / "templates/studio_raha/index.html").read_text(encoding="utf-8")
        self.assertNotIn('id="newsletterForm"', text)
        self.assertNotIn("$('#newsletterForm')", text)
        self.assertNotIn('id="emailInput"', text)
        self.assertIn("opening a draft does not send a message", text)
        self.assertIn("mailto:hello@mojplaywin.com", text)

    def test_building_clinic_does_not_claim_local_file_is_sent(self):
        text = (ROOT / "public/mohammad/index.html").read_text(encoding="utf-8")
        self.assertIn("فرم درخواست را به سرور ارسال نمی‌کند", text)
        self.assertIn("ساخت فایل محلی به معنی ثبت روی سرور", text)
        self.assertIn('href="/ask-master/index.php?service=1"', text)

    def test_mojplaywin_guest_invoice_not_assumed_paid(self):
        text = (ROOT / "core/templates/mojplaywin/store.html").read_text(encoding="utf-8")
        self.assertIn("unconfirmed TRX transfer is not proof", text)
        self.assertIn("server", text)
        self.assertIn("valid email address", text)

    def test_auction_inquiry_not_fake_bid(self):
        text = (ROOT / "core/templates/core/auctions.html").read_text(encoding="utf-8")
        self.assertIn("به معنی پیشنهاد قیمت، حضور در مزایده یا پذیرش قرارداد نیست", text)
        self.assertIn('class="auction-inquiry"', text)

    def test_no_automatic_newsletter_email_sent(self):
        for path in ("templates/studio_raha/index.html",
                     "templates/taniya_studio/index.html"):
            with self.subTest(path=path):
                text = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn("mailto:hello@mojplaywin.com", text)

    def test_expert_quote_is_not_misrepresented_as_paid_order(self):
        for marker, path, _, action in SURFACES:
            if marker in {"R07", "R08", "R09", "R11", "R16", "R17"}:
                with self.subTest(marker=marker):
                    text = (ROOT / path).read_text(encoding="utf-8")
                    self.assertIn(action, text)
                    self.assertNotIn("data-revenue-confirmed-payment=\"true\"", text)


if __name__ == "__main__":
    unittest.main()
