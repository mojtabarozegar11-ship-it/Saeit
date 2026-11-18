"""Read-only first-party support fallback contract for real MOJ-PROP-01.

No network, sending mail, buyer POST, payment or production mutation occurs.
A page is not an accepted CRM opt-in or a proven deliverable email.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.mojprop_public_official_contact_contract_c127 import (
    classify_contact, classify_transport, parse_transport,
)

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "templates/moj-prop/contact/index.html"
WORKFLOW = ROOT / ".github/workflows/mojprop-public-readonly-24h-evidence-20261115.yml"
SCRIPT = ROOT / "scripts/mojprop_public_official_contact_contract_c127.py"


def transport(*, http="200", exit_code="0", redirects="0"):
    return (
        "GET_ONLY_mojprop_contact_HTTP=" + http + "\n"
        "GET_ONLY_mojprop_contact_CURL_EXIT=" + exit_code + "\n"
        "GET_ONLY_mojprop_contact_REDIRECTS=" + redirects + "\n"
    )


class ContactFallbackProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PAGE.read_text("utf-8")
        cls.workflow = WORKFLOW.read_text("utf-8")

    def test_authentic_source_is_a_nonpayable_manual_support_page(self):
        self.assertTrue(classify_contact(self.html.encode()))

    def test_only_published_mojplaywin_mailto_is_present(self):
        self.assertIn(
            "mailto:support@mojplaywin.com?subject=MOJ-PROP-01%20Prelaunch%20Information%20Request",
            self.html,
        )
        self.assertTrue(classify_contact(self.html.encode()))
        self.assertNotIn("mojtaba.rozegar11@gmail.com", self.html)

    def test_contact_support_does_not_fake_generic_plan1_crm(self):
        self.assertNotIn('/moj-prop/#request', self.html)
        self.assertIn("<strong>not</strong> a verified Plan 1 lead", self.html)
        self.assertTrue(classify_contact(self.html.encode()))
        self.assertIn("nothing is sent automatically", self.html)

    def test_no_automatic_email_form_or_active_js(self):
        self.assertNotIn("<form", self.html)
        self.assertNotIn("<script", self.html)
        self.assertIn("no payment details or private credentials", self.html)

    def test_generic_other_service_request_is_not_promoted_as_plan1(self):
        self.assertFalse(classify_contact(
            self.html.replace('href="/moj-prop/"', 'href="/moj-prop/#request"').encode()
        ))

    def test_wrong_or_private_email_is_refused(self):
        bad = self.html.replace(
            "mailto:support@mojplaywin.com?subject=",
            "mailto:unverified@example.org?subject=",
        )
        self.assertFalse(classify_contact(bad.encode()))

    def test_auto_submit_script_is_refused(self):
        bad = self.html.replace("</body>", "<script>fetch('/post')</script></body>")
        self.assertFalse(classify_contact(bad.encode()))

    def test_auto_post_form_is_refused(self):
        bad = self.html.replace("</body>", '<form method="post"></form></body>')
        self.assertFalse(classify_contact(bad.encode()))

    def test_stale_page_lacking_prelaunch_risk_warning_is_refused(self):
        bad = self.html.replace("no payment details or private credentials", "send funds now")
        self.assertFalse(classify_contact(bad.encode()))

    def test_bogus_contact_page_with_http200_is_not_accepted(self):
        bogus = b"<html><title>Welcome</title><body>200 OK</body></html>"
        self.assertFalse(classify_contact(bogus))

    def test_scriptless_but_missing_plan1_mailto_is_refused(self):
        bad = self.html.replace(
            "MOJ-PROP-01%20Prelaunch%20Information%20Request",
            "Other%20Program",
        )
        self.assertFalse(classify_contact(bad.encode()))

    def test_scriptless_active_markup_bypasses_are_all_rejected(self):
        # 25 distinct adversarial HTML/CSS constructs: none may be called a
        # safe first-party support fallback just because script/form=0.
        attacks = (
            '<iframe src="https://attacker.invalid/x"></iframe>',
            '<img src="https://attacker.invalid/pixel">',
            '<svg onload="alert(1)"></svg>',
            '<meta http-equiv="refresh" content="0;url=https://attacker.invalid">',
            '<a href="/moj-prop/" onclick="steal()">click</a>',
            '<link rel="stylesheet" href="https://attacker.invalid/x.css">',
            '<base href="https://attacker.invalid/">',
            '<video src="/x.mp4"></video>',
            '<audio src="/x.mp3"></audio>',
            '<object data="https://attacker.invalid/x"></object>',
            '<embed src="/x">',
            '<input name="private">',
            '<button formaction="/buyer-post">send</button>',
            '<canvas></canvas>',
            '<template><span>deceptive</span></template>',
            '<picture><source srcset="https://attacker.invalid/img"></picture>',
            '<a href="/moj-prop/" ping="https://attacker.invalid">home</a>',
            '<a href="/moj-prop/" style="display:none">home</a>',
            '<div onmouseover="fetch(1)">hover</div>',
            '<div onfocus="fetch(1)">focus</div>',
            '<style>@import "https://attacker.invalid/style.css";</style>',
            '<style>p{background:url(https://attacker.invalid/t)}</style>',
            '<style>p{width:expression(alert(1))}</style>',
            '<style>p{behavior:url(steal.htc)}</style>',
            '<style>p{background:u\\72l(https://attacker.invalid)}</style>',
        )
        for payload in attacks:
            with self.subTest(payload=payload[:54]):
                changed = self.html.replace("</body>", payload + "</body>")
                self.assertNotEqual(changed, self.html)
                self.assertFalse(classify_contact(changed.encode("utf-8")))

    def test_public_transport_direct_200_and_no_redirect_only(self):
        good = parse_transport(transport())
        self.assertTrue(classify_transport(good))
        for kwargs in (
            {"http": "404"},
            {"http": "500"},
            {"http": "301"},
            {"http": "000", "exit_code": "6"},
            {"exit_code": "28"},
            {"redirects": "1"},
            {"redirects": "unknown"},
        ):
            with self.subTest(kwargs=kwargs):
                self.assertFalse(classify_transport(parse_transport(transport(**kwargs))))

    def test_missing_duplicate_or_invalid_transport_metadata_is_rejected(self):
        for bad in (
            transport() + transport().splitlines()[0] + "\n",
            transport().replace("GET_ONLY_mojprop_contact_REDIRECTS=0\n", ""),
            transport().replace("HTTP=200", "HTTP=poison"),
            transport() + "csrf_token=PRIVATE\n",
            transport() + "receipt_token=PRIVATE\n",
            transport() + "buyer_email=private@example.com\n",
            transport() + ("A" * 700),
        ):
            with self.subTest(hint=bad[:38]):
                self.assertIsNone(parse_transport(bad))

    def test_unknown_route_status_does_not_pass(self):
        self.assertFalse(classify_transport(None))
        self.assertFalse(classify_contact(b""))

    def test_workflow_collects_contact_as_independent_sanitized_evidence(self):
        self.assertIn("GET_ONLY_mojprop_contact_HTTP=%s", self.workflow)
        self.assertIn("GET_ONLY_mojprop_contact_CURL_EXIT=%s", self.workflow)
        self.assertIn("GET_ONLY_mojprop_contact_REDIRECTS=%s", self.workflow)
        self.assertIn('chmod 600 "$support_transport_proof"', self.workflow)
        self.assertIn('"$check_dir/mojprop_contact.body"', self.workflow)
        self.assertIn("mojprop_public_official_contact_contract_c127.py", self.workflow)
        self.assertIn("NO_POST_NO_PAYMENT_NO_RELEASE=true", self.workflow)

    def test_source_only_valid_receipt_does_not_claim_email_delivery(self):
        with tempfile.TemporaryDirectory() as td:
            contact = Path(td) / "contact.html"
            evidence = Path(td) / "transport.txt"
            summary = Path(td) / "summary.md"
            contact.write_text(self.html, "utf-8")
            evidence.write_text(transport(), "utf-8")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), str(contact), str(evidence), str(summary)],
                capture_output=True, text=True, check=False, timeout=8,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("GET_ONLY_SUPPORT_PAGE_PRESENT_NOT_DELIVERY", run.stdout)
            self.assertIn("VERIFIED_LEAD=false", run.stdout)
            self.assertIn("MESSAGE_SENT=false", run.stdout)
            self.assertIn("Mail delivery / consented CRM lead / paid order: NOT VERIFIED", summary.read_text("utf-8"))

    def test_offline_bad_live_contact_is_blocked_even_with_valid_200(self):
        with tempfile.TemporaryDirectory() as td:
            contact = Path(td) / "contact.html"
            evidence = Path(td) / "transport.txt"
            summary = Path(td) / "summary.md"
            contact.write_text("<html><title>Welcome</title>OK</html>", "utf-8")
            evidence.write_text(transport(), "utf-8")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), str(contact), str(evidence), str(summary)],
                capture_output=True, text=True, check=False, timeout=8,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("OFFICIAL_CONTACT_GATE=BLOCKED", run.stdout)
            self.assertNotIn("GET_ONLY_SUPPORT_PAGE_PRESENT_NOT_DELIVERY", run.stdout)

    def test_symlink_html_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            actual = Path(td) / "real.html"
            link = Path(td) / "link.html"
            evidence = Path(td) / "transport.txt"
            summary = Path(td) / "summary.md"
            actual.write_text(self.html, "utf-8")
            link.symlink_to(actual)
            evidence.write_text(transport(), "utf-8")
            run = subprocess.run(
                [sys.executable, str(SCRIPT), str(link), str(evidence), str(summary)],
                capture_output=True, text=True, check=False, timeout=8,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("OFFICIAL_CONTACT_GATE=BLOCKED", run.stdout)

    def test_symlink_summary_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            contact = Path(td) / "contact.html"
            evidence = Path(td) / "transport.txt"
            actual = Path(td) / "private.txt"
            link = Path(td) / "summary.md"
            contact.write_text(self.html, "utf-8")
            evidence.write_text(transport(), "utf-8")
            actual.write_text("unchanged", "utf-8")
            link.symlink_to(actual)
            run = subprocess.run(
                [sys.executable, str(SCRIPT), str(contact), str(evidence), str(link)],
                capture_output=True, text=True, check=False, timeout=8,
            )
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(actual.read_text("utf-8"), "unchanged")


if __name__ == "__main__":
    unittest.main()
