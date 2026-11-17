"""Privacy-safe C128 live contact drift: all diagnostics are fixed booleans.

Runs on synthetic and reviewed STATIC HTML bytes only; no public network,
buyer information, external mail, DB, deployment or payment action.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.mojprop_public_contact_drift_c128 import _CHECKS, checks, safe_read
from scripts.mojprop_public_official_contact_contract_c127 import (
    _safe_contact_href, classify_contact,
)

ROOT=Path(__file__).resolve().parents[1]
PAGE=ROOT/"templates/moj-prop/contact/index.html"
RUNNER=ROOT/"scripts/mojprop_public_contact_drift_c128.py"
WORKFLOW=ROOT/".github/workflows/mojprop-public-readonly-24h-evidence-20261115.yml"


class ContactDriftC128Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=PAGE.read_bytes()

    def flag(self, code: bytes, key: str, *, reviewed: bytes | None = None):
        return checks(code, self.original if reviewed is None else reviewed)[key]

    def test_real_reviewed_source_passes_all_fixed_checks(self):
        d=checks(self.original,self.original)
        self.assertEqual(tuple(d),_CHECKS)
        self.assertTrue(all(d.values()),d)

    def test_same_valid_semantics_but_changed_bytes_not_claimed_exact(self):
        modified=self.original.replace(b"<!--",b"<!-- ",1) if b"<!--" in self.original else self.original.replace(b"</html>",b"<!-- harmless -->\n</html>")
        d=checks(modified,self.original)
        self.assertTrue(d["complete_contact_contract"])
        self.assertFalse(d["exact_reviewed_template_bytes"])

    def test_missing_reviewed_template_does_not_fake_parity(self):
        d=checks(self.original,None)
        self.assertFalse(d["exact_reviewed_template_bytes"])
        self.assertTrue(d["complete_contact_contract"])

    def test_legacy_generic_form_anchor_explicitly_fails(self):
        bad=self.original.replace(b'href="/moj-prop/"',b'href="/moj-prop/#request"')
        self.assertFalse(self.flag(bad,"legacy_generic_form_absent"))
        self.assertFalse(self.flag(bad,"complete_contact_contract"))

    def test_login_or_non_mojprop_page_is_detected_without_content_leak(self):
        bad=b'<html><head><title>Account sign-in</title></head><body>Please log in</body></html>'
        d=checks(bad,self.original)
        self.assertTrue(d["html_document"])
        self.assertFalse(d["plan1_title"])
        self.assertFalse(d["plan1_subject_mailto"])
        self.assertFalse(d["complete_contact_contract"])

    def test_missing_specific_plan1_mailto_is_marked(self):
        bad=self.original.replace(b"MOJ-PROP-01%20Prelaunch%20Information%20Request",b"Other%20Product")
        self.assertFalse(self.flag(bad,"plan1_subject_mailto"))
        self.assertFalse(self.flag(bad,"complete_contact_contract"))

    def test_wrong_support_address_does_not_pass_either_contract(self):
        bad=self.original.replace(b"support@mojplaywin.com",b"other@unapproved.test")
        d=checks(bad,self.original)
        self.assertFalse(d["official_support_visible"])
        self.assertFalse(d["plan1_subject_mailto"])
        self.assertFalse(d["complete_contact_contract"])

    def test_script_is_detected_and_disallowed(self):
        bad=self.original.replace(b"</body>",b"<script>sendPrivate()</script></body>")
        d=checks(bad,self.original)
        self.assertFalse(d["script_free"])
        self.assertFalse(d["complete_contact_contract"])

    def test_post_form_is_detected_and_disallowed(self):
        bad=self.original.replace(b"</body>",b'<form method="post"></form></body>')
        d=checks(bad,self.original)
        self.assertFalse(d["form_free"])
        self.assertFalse(d["complete_contact_contract"])

    def test_missing_no_payment_warning_is_detected(self):
        bad=self.original.replace(b"no payment details or private credentials",b"pay us immediately")
        self.assertFalse(self.flag(bad,"no_payment_credentials_warning"))
        self.assertFalse(self.flag(bad,"complete_contact_contract"))

    def test_missing_no_crm_disclaimer_is_detected(self):
        bad=self.original.replace(b"<strong>not</strong> a verified Plan 1 lead",b"an accepted Plan 1 lead")
        self.assertFalse(self.flag(bad,"support_is_not_crm_lead"))
        self.assertFalse(self.flag(bad,"complete_contact_contract"))

    def test_missing_automatic_send_disclaimer_is_detected(self):
        bad=self.original.replace(b"nothing is sent automatically",b"this link sends automatically")
        self.assertFalse(self.flag(bad,"no_auto_email_notice"))
        self.assertFalse(self.flag(bad,"complete_contact_contract"))

    def test_protocol_relative_external_link_bypass_rejected(self):
        self.assertFalse(_safe_contact_href("//evil.example/steal"))
        bad=self.original.replace(b'href="/moj-prop/"',b'href="//evil.example/steal"')
        d=checks(bad,self.original)
        self.assertFalse(d["all_links_first_party"])
        self.assertFalse(d["complete_contact_contract"])
        self.assertFalse(classify_contact(bad))

    def test_backslash_external_link_bypass_rejected(self):
        self.assertFalse(_safe_contact_href("/\\\\evil.example/steal"))
        bad=self.original.replace(b'href="/moj-prop/"',b'href="/\\\\evil.example/steal"')
        d=checks(bad,self.original)
        self.assertFalse(d["all_links_first_party"])
        self.assertFalse(d["complete_contact_contract"])

    def test_controls_and_hidden_linebreak_in_href_rejected(self):
        for href in ("/moj-prop/\n", "/moj-prop/\r", "#section\x00", "/moj-prop/\t"):
            with self.subTest(href=repr(href)):
                self.assertFalse(_safe_contact_href(href))

    def test_valid_first_party_paths_and_only_two_mailto_values_allowed(self):
        self.assertTrue(_safe_contact_href("/moj-prop/"))
        self.assertTrue(_safe_contact_href("#main"))
        self.assertFalse(_safe_contact_href("https://somewhere.example"))
        self.assertFalse(_safe_contact_href("mailto:unverified@example.com"))

    def test_oversize_and_non_utf8_fail_closed(self):
        self.assertTrue(not any(checks(b"x"*(256*1024+1),self.original).values()))
        self.assertTrue(not any(checks(b"\xff",self.original).values()))

    def test_missing_or_symlink_html_are_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            target=folder/"real.html"
            target.write_bytes(self.original)
            link=folder/"link.html"
            link.symlink_to(target)
            self.assertIsNone(safe_read(link))
            self.assertIsNone(safe_read(folder/"none.html"))
            self.assertEqual(safe_read(target),self.original)

    def test_cli_prints_fixed_keys_only_and_no_html_or_email_address(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"live.html"
            q=Path(temp)/"source.html"
            p.write_bytes(self.original)
            q.write_bytes(self.original)
            z=subprocess.run(
                [sys.executable,str(RUNNER),str(p),str(q)],
                check=False,capture_output=True,text=True,timeout=8,
            )
            self.assertEqual(z.returncode,0,z.stderr)
            self.assertIn("MOJPROP_C128_COMPLETE_CONTACT_CONTRACT=true",z.stdout)
            self.assertIn("MOJPROP_C128_LIVE_RUNTIME_SOURCE_PROVEN=false",z.stdout)
            self.assertIn("MOJPROP_C128_PAYMENT_OR_EMAIL=false",z.stdout)
            self.assertNotIn("support@mojplaywin.com",z.stdout)
            self.assertNotIn("<html",z.stdout.lower())
            lines=z.stdout.splitlines()
            self.assertEqual(len(lines),len(_CHECKS)+3)
            self.assertTrue(all(x.endswith(("=true","=false")) for x in lines))

    def test_workflow_has_get_only_body_without_logging_sensitive_values(self):
        wf=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("mojprop_public_contact_drift_c128.py",wf)
        self.assertIn('"$check_dir/mojprop_contact.body"',wf)
        self.assertIn('"templates/moj-prop/contact/index.html"',wf)
        self.assertIn("NO_POST_NO_PAYMENT_NO_RELEASE=true",wf)


if __name__=="__main__":
    unittest.main()
