"""C153 public-static cutover contract; never live lead/checkout proof."""
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "templates/moj-prop-v4/index.html"
CONTACT = ROOT / "templates/moj-prop/contact/index.html"
INSTALLER = ROOT / ".github/workflows/mojplaywin-moj-prop-deploy.yml"


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []
    def handle_starttag(self, tag, pairs):
        if tag == "a":
            self.hrefs.append(dict(pairs).get("href", ""))


class Plan1StaticTruth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = HOME.read_text(encoding="utf-8")
        cls.contact = CONTACT.read_text(encoding="utf-8")
        cls.workflow = INSTALLER.read_text(encoding="utf-8")
        cls.hlinks, cls.clinks = Links(), Links()
        cls.hlinks.feed(cls.home)
        cls.clinks.feed(cls.contact)

    def test_01_real_plan1_instead_of_educational_starter(self):
        self.assertIn("SOLE CURRENT PRODUCT", self.home)
        self.assertIn("MOJ-PROP-01", self.home)
        self.assertIn("30,000,000 SUN", self.home)
        self.assertNotIn("MOJPROP-STARTER30", self.home)
        self.assertIn("proposed future challenge", self.home)

    def test_02_explicit_prelaunch_no_payment_or_live_broker_promise(self):
        for page in (self.home, self.contact):
            self.assertIn("prelaunch", page.lower())
            self.assertIn("no payment", page.lower())
        self.assertIn("independently verified capital", self.home)
        self.assertIn("not an accepted plan 1 crm lead", self.home.lower())

    def test_03_no_clickable_known_unavailable_404_form(self):
        for page in (self.hlinks, self.clinks):
            self.assertFalse(any(url.startswith("/moj-prop-interest/form/")
                                 for url in page.hrefs), page.hrefs)
        self.assertIn("Dedicated Plan 1 form not live", self.home)
        self.assertIn("Dedicated Plan 1 form not live", self.contact)

    def test_04_voluntary_first_party_support_fallback_not_crm_claim(self):
        self.assertIn('href="/moj-prop/contact/"', self.home)
        self.assertIn("Support contact is NOT an accepted Plan 1 CRM lead", self.home)
        self.assertIn('mailto:support@mojplaywin.com?subject=MOJ-PROP-01', self.contact)
        self.assertIn("nothing is sent automatically", self.contact.lower())

    def test_05_other_service_intake_is_not_paid_plan1(self):
        self.assertIn("const endpoint='/moj-prop-intake/'", self.home)
        self.assertIn("Generic services must not infer a funded-challenge SKU", self.home)
        self.assertNotIn('action="/moj-prop-interest/"', self.home)
        self.assertNotIn("tronweb.trx.sendtransaction", self.home.lower())

    def test_06_page_is_standalone_and_resolves_html(self):
        for page in (self.home, self.contact):
            p = Links()
            p.feed(page)
            self.assertNotIn('src="/app.js"', page)
            self.assertNotIn('href="/styles.css"', page)

    def test_07_existing_legacy_deployer_checks_real_plan1_not_educational_phrase(self):
        self.assertIn("SOLE CURRENT PRODUCT", self.workflow)
        self.assertIn('"MOJ-PROP-01"', self.workflow)
        self.assertNotIn('"See service prices"', self.workflow)
        self.assertIn('assert "SOLE CURRENT PRODUCT" in home', self.workflow)
        self.assertIn('assert "MOJ-PROP-01" in home', self.workflow)

    def test_08_production_release_still_requires_owner_dispatch(self):
        self.assertIn("owner_approved_static_release", self.workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'", self.workflow)
        self.assertIn("github.ref == 'refs/heads/main'", self.workflow)

    def test_09_static_no_external_checkout_or_wallet_action(self):
        for p in (self.hlinks, self.clinks):
            self.assertFalse(any("/checkout/" in link or
                                 "/moj-prop/pay/" in link for link in p.hrefs))
        self.assertNotIn("walletconnect", self.home.lower())

    def test_12_main_before_plan1_source_is_review_pinned_and_admitted_only_once(self):
        script = (ROOT / "scripts/update_mojplaywin_moj_prop_catalog.py").read_text("utf-8")
        baseline = ROOT / "templates/moj-prop-v4/baselines/index-main-before-plan1-c153.html"
        import hashlib
        data = baseline.read_bytes()
        blob = b"blob " + str(len(data)).encode("ascii") + b"\\0" + data
        expected = "30b7fe4400f88252f3b71a581f96a796ca853b6c"
        self.assertEqual(hashlib.sha1(blob).hexdigest(), expected)
        self.assertIn(f'BASELINE_MAIN_HOME_GIT_BLOB = "{expected}"', script)
        self.assertIn("exact_pre_plan1_home", script)
        self.assertIn("Unreviewed current-main homepage baseline denied", script)
        self.assertNotEqual(data, HOME.read_bytes())

    def test_11_contact_source_is_in_install_and_rollback_inventory(self):
        script = (ROOT / "scripts/update_mojplaywin_moj_prop_catalog.py").read_text("utf-8")
        self.assertIn('Path("contact/index.html")', script)
        self.assertIn('BASELINE_CONTACT', script)
        self.assertIn("Live Plan1 contact differs from approved baseline", script)
        self.assertIn("v4-contact-rollback", script)
        stage = ROOT / "templates/moj-prop-v4/contact/index.html"
        baseline = ROOT / "templates/moj-prop-v4/baselines/contact-index-pre-plan1.html"
        self.assertEqual(stage.read_text("utf-8"), self.contact)
        self.assertTrue(baseline.is_file())
        self.assertNotEqual(baseline.read_bytes(), stage.read_bytes())

    def test_10_farsi_prelaunch_caveat_and_first_party_contact(self):
        self.assertIn("فرم اختصاصی رضایت فعلاً فعال نیست", self.home)
        self.assertIn("فرم اختصاصی رضایت فعلاً فعال نیست", self.contact)
        self.assertIn("MOJ-PROP-01", self.contact)
