"""C110 Moj Prop manual-contact continuity; source only, no outbound mail."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = "support@mojplaywin.com"
MAILTO = "mailto:support@mojplaywin.com?subject=Moj%20Prop%20Manual%20Service%20Enquiry"


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs).get("href", ""))


class MojPropManualSupportFallbackTests(unittest.TestCase):
    def test_published_support_identity_is_not_a_new_or_unverified_address(self):
        published = (ROOT / "scripts/mpw_dynamic_main_shell_20261019.php").read_text()
        self.assertIn("$mail='support@mojplaywin.com';", published)

    def test_v4_main_customer_page_keeps_actual_request_and_fallback(self):
        page = (ROOT / "templates/moj-prop-v4/index.html").read_text()
        links = _Links()
        links.feed(page)
        self.assertIn("/contact/", links.links)
        self.assertNotIn(MAILTO, links.links)
        self.assertNotIn("mailto:", page.lower())
        # Plan1 is not a blueprint request. Its consent form is a separate
        # first-party route, backed by an actual server POST/CSRF contract.
        self.assertIn("/moj-prop-interest/form/", links.links)
        self.assertNotIn("/moj-prop-intake/?format=html", links.links)
        self.assertIn("If the form is unavailable", page)
        self.assertIn("No response time is guaranteed", page)
        self.assertNotIn("mojtaba.rozegar11@gmail.com", page)
        self.assertIn("never send passwords, wallet keys or payment", page)

    def test_legacy_contact_keeps_fallback_without_personal_email_or_payment(self):
        page = (ROOT / "templates/moj-prop/contact/index.html").read_text()
        links = _Links()
        links.feed(page)
        self.assertIn(MAILTO, links.links)
        self.assertNotIn("mojtaba.rozegar11@gmail.com", page)
        self.assertIn("/moj-prop/#plan-one", links.links)
        self.assertIn("/moj-prop-interest/form/", links.links)
        self.assertIn("no payment details or private credentials", page)
        self.assertIn("No guaranteed response time", page)

    def test_main_push_cannot_auto_publish_updated_static_pages(self):
        workflow = (ROOT / ".github/workflows/mojplaywin-moj-prop-deploy.yml").read_text()
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)
        self.assertIn("MOJPROP_FULL_DB_APP_MEDIA_RESTORE_VERIFIED", workflow)
        self.assertIn("MOJPROP_STATIC_ROLLBACK_VERIFIED", workflow)
        self.assertIn("MOJPROP_PASSENGER_TENANT_ISOLATION_VERIFIED", workflow)


if __name__ == "__main__":
    unittest.main()
