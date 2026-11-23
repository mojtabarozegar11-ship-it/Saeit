"""Source regression for the exact two-hop MojPlayWin public contact URL.

Only static GitHub workflow and URL source are inspected; no HTTP requests,
forms, customer data, emails, payment, DNS or production mutation.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LIVE_OBSERVER = ROOT / ".github/workflows/mojprop-public-readonly-24h-evidence-20261115.yml"
NEW_OBSERVER = ROOT / ".github/workflows/mpw-contact-redirect-readonly-20261123.yml"
URLS = ROOT / "config/urls.py"


class MojPlayWinContactTwoHopRegressions(unittest.TestCase):
    def test_actual_public_contact_is_kept_as_the_canonical_probe(self):
        data = LIVE_OBSERVER.read_text("utf-8")
        self.assertIn('"mpw_contact|https://mojplaywin.com/contact/"', data)
        self.assertIn('"mojprop_contact|https://mojplaywin.com/moj-prop/contact/"', data)
        self.assertIn('redirect_limit=1', data)
        self.assertIn('[[ "$name" == "mpw_contact" ]] && redirect_limit=3', data)
        self.assertIn('curl --proto \'=https\' --tlsv1.2 -L --max-redirs "$redirect_limit"', data)
        self.assertIn('GET_ONLY_', data)

    def test_no_unreviewed_root_url_remap_or_payment_release(self):
        urls = URLS.read_text("utf-8")
        self.assertIn('path("contact/", RedirectView.as_view(url="/ask-master/index.php?service=1", permanent=False)', urls)
        self.assertNotIn("curl --request POST", NEW_OBSERVER.read_text("utf-8"))
        self.assertIn('NO_POST_NO_PAYMENT_NO_CUSTOMER_DATA=true', NEW_OBSERVER.read_text("utf-8"))
        self.assertIn('READONLY_EXTERNAL_RUNNER=true', NEW_OBSERVER.read_text("utf-8"))

    def test_monitor_keeps_single_bot_dns_error_separate_from_cpanel_reachability(self):
        data = LIVE_OBSERVER.read_text("utf-8")
        self.assertIn('[[ "$name" == "single_bot_root" ]] || mojplaywin_unhealthy=', data)
        self.assertIn('single_bot_root|https://mojtaba.bot.ai/', data)
        self.assertIn('mojplaywin_unhealthy=0', data)

    def test_readonly_audit_uses_bounded_same_host_public_routes(self):
        data = NEW_OBSERVER.read_text("utf-8")
        self.assertIn('https://mojplaywin.com/contact/', data)
        self.assertIn('https://mojplaywin.com/mpw-editorial/revenue/inquiry.php?service=general', data)
        self.assertIn('https://mojplaywin.com/moj-prop/contact/', data)
        self.assertIn('--max-redirs 6 --location', data)
        self.assertIn('--retry 0', data)
        self.assertNotIn('secrets.', data)
        self.assertNotIn('ssh ', data)
        self.assertNotIn('curl -X POST', data)


if __name__ == "__main__":
    unittest.main()
