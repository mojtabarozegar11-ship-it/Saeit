"""Cross-site commercial source contracts: do not assert production deployment."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "mojtaba_revenue_portfolio", ROOT/"scripts/mojtaba_revenue_portfolio.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def source(code):
    return (ROOT/module.OFFERS[code].source).read_text("utf8")

class RevenueSourceContracts(unittest.TestCase):
    def test_every_source_is_in_repository_not_parent_directory(self):
        for offer in module.OFFERS.values():
            with self.subTest(offer=offer.code):
                p=(ROOT/offer.source).resolve()
                self.assertTrue(p.is_relative_to(ROOT.resolve()))
                self.assertTrue(p.is_file())
                self.assertTrue(offer.path.startswith("/"))

    def test_farm_public_cta_is_existing_contact_route(self):
        s=source("farm_economics")
        self.assertEqual(s.count('id="farm-break-even-inquiry"'),1)
        self.assertIn('href="/contact/"',s)
        self.assertIn("نقطه سربه‌سر",s)

    def test_farm_brief_has_three_input_fields_as_guidance(self):
        s=source("farm_economics")
        for phrase in ("محدوده زمانی", "داده", "حساسیت هزینه", "تأیید موردی"):
            self.assertIn(phrase,s)

    def test_main_en_and_legacy_offer_stay_aligned(self):
        sources=(source("website_diagnosis"),source("website_bounded_repair"))
        for s in sources:
            self.assertEqual(s.count('id="website-checkout-inquiry"'),1)
            self.assertIn("mailto:mojplaywin@gmail.com?subject=",s)
            self.assertIn("USD 29",s)
            self.assertIn("USD 79",s)
            self.assertIn("Expected",s)
            self.assertIn("without",s.lower())

    def test_no_new_wallet_payment_or_broker_in_service_section(self):
        for code in ("website_diagnosis", "website_bounded_repair"):
            s=source(code)
            snippet=s.split('id="website-checkout-inquiry"',1)[1].split("</section>",1)[0]
            for forbidden in ("Pay now","Buy now","connect wallet","place trade",
                              "execute order","100% guaranteed"):
                self.assertNotIn(forbidden,snippet)

    def test_cafe_existing_form_collects_consent_not_payment(self):
        s=source("cafe_b2b")
        self.assertIn('id="cafeInquiry"',s)
        self.assertIn('name="consent" type="checkbox" required',s)
        self.assertIn('/ask-master/index.php',s)

    def test_company_catalog_existing_price_not_fake_sale(self):
        s=source("company_catalog")
        self.assertIn('WHERE enabled=1',s)
        self.assertIn('number_format((int)$p[\'price_irr\'])',s)
        self.assertIn("پرداخت آنلاین تا اتصال درگاه غیرفعال است",s)

    def test_industrial_and_research_paths_are_existing(self):
        s=source("industrial_feasibility")
        self.assertIn('request.path == "/industry/"',s)
        self.assertIn('request.path == "/research/"',s)

    def test_unproven_products_cannot_be_listed_as_live_by_policy(self):
        for code in ("digital_publication", "game_license", "trading_education"):
            self.assertEqual(module.OFFERS[code].proof,"proposed_not_listed")
            self.assertEqual(module.OFFERS[code].lawful_channel,"manual_review_only")

    def test_one_canonical_bot_and_no_new_http_endpoint(self):
        s=(ROOT/"scripts/mojtaba_revenue_portfolio.py").read_text("utf8")
        self.assertIn('CANONICAL_BOT = "mojtaba.bot.ai"',s)
        self.assertNotIn("from django.urls",s)
        self.assertNotIn("socket",s)
        self.assertNotIn("websocket",s)

    def test_all_revenue_cli_paths_share_the_strict_input_reader(self):
        source = (ROOT / "scripts/mojtaba_revenue_cli.py").read_text("utf8")
        self.assertIn("from revenue_intake_io import read_strict_json", source)
        self.assertIn("read_strict_json(file_path, max_bytes=MAX_BYTES)", source)
        self.assertIn("MAX_BYTES = 32768", source)
        self.assertNotIn('json.loads(raw.decode("utf-8"))', source)

    def test_qualifier_and_main_catalogue_share_secure_output_writer(self):
        core = (ROOT / "scripts/mojtaba_revenue_cli.py").read_text("utf8")
        two = (ROOT / "scripts/revenue_dual_offer_qualifier.py").read_text("utf8")
        self.assertIn("write_new_anonymized_json(target, text)", core)
        self.assertIn("write_new_anonymized_json(args.output, serialized)", two)

    def test_size_and_depth_limits_are_not_waived_by_synthetic_mode(self):
        io = (ROOT / "scripts/revenue_intake_io.py").read_text("utf8")
        self.assertIn("MAX_BYTES = 65536", io)
        self.assertIn("MAX_JSON_DEPTH = 64", io)
        self.assertIn("MAX_JSON_NODES = 4096", io)
        self.assertIn("intake changed during read", io)
        self.assertIn("os.O_EXCL", io)

    def test_large_synthetic_counts_cannot_exhaust_financial_preview(self):
        p = (ROOT / "scripts/mojtaba_revenue_portfolio.py").read_text("utf8")
        self.assertIn("MAX_SYNTHETIC_COUNT = 1_000_000_000", p)
        self.assertIn("MAX_SOURCE_CHECKS = 1_000_000", p)
        self.assertIn("MAX_SYNTHETIC_COUNT for x in _KPI_KEYS", p)
        self.assertIn("source_check_passes <= MAX_SOURCE_CHECKS", p)

    def test_cli_suite_is_registered_without_payment_or_deployment(self):
        wf = (ROOT / ".github/workflows/revenue-p0-source-only.yml").read_text("utf8")
        self.assertIn("test_mojtaba_revenue*.py", wf)
        self.assertIn("test_revenue_*.py", wf)
        self.assertNotIn("push: main", wf)
        self.assertNotIn("pay_now", wf)
        self.assertNotIn("transaction.submit", wf)

    def test_source_status_remains_not_paid_or_deployed(self):
        cli = (ROOT / "scripts/mojtaba_revenue_cli.py").read_text("utf8")
        self.assertIn("CANONICAL_BOT", cli)
        src = (ROOT / "scripts/mojtaba_revenue_portfolio.py").read_text("utf8")
        self.assertIn('CANONICAL_BOT = "mojtaba.bot.ai"', src)
        self.assertIn('"collected_revenue": None', src)
        self.assertIn('"payment_verified": False', src)
        self.assertIn('"production_deployed": False', src)


if __name__=="__main__":
    unittest.main()
