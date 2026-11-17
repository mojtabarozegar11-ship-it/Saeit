"""C155 bounded public source-drift classifier; all fake HTTP responses."""
import hashlib
import unittest
from unittest.mock import patch

from scripts import mojprop_c155_public_static_source_readonly as probe


class SourceAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = probe.allowed_snapshots()

    def test_pinned_original_sources_are_real_exact_git_blobs(self):
        for filename, git_id in (
            ("baselines/index-main-before-plan1-c153.html", probe.GIT_HOME_BLOB),
            ("baselines/contact-index-pre-plan1.html", probe.GIT_CONTACT_BLOB),
        ):
            raw = (probe.ROOT / filename).read_bytes()
            header = b"blob " + str(len(raw)).encode("ascii") + b"\0"
            self.assertEqual(hashlib.sha1(header + raw).hexdigest(), git_id)

    def test_current_main_home_is_accepted_without_approval_to_deploy(self):
        result = probe.classify(self.snap["home"]["known_current_main"],
                                self.snap["home"])
        self.assertEqual(result, "known_current_main")

    def test_legacy_home_and_markerless_are_supported_as_reviewed_only(self):
        for key in ("known_legacy_v4", "known_legacy_v4_markerless"):
            with self.subTest(key=key):
                self.assertNotEqual(probe.classify(self.snap["home"][key],
                                                    self.snap["home"]),
                                    "unreviewed_or_unavailable")

    def test_proposed_plan1_and_contact_have_exact_source_class(self):
        for name in ("home", "contact"):
            self.assertEqual(
                probe.classify(self.snap[name]["approved_plan1_source"],
                               self.snap[name]),
                "approved_plan1_source",
            )

    def test_owner_append_is_not_automatically_accepted(self):
        raw = self.snap["home"]["known_current_main"] + b"<!-- owner edit -->"
        self.assertEqual(probe.classify(raw, self.snap["home"]),
                         "unreviewed_or_unavailable")

    def test_single_byte_substitution_fails_closed(self):
        raw = self.snap["contact"]["known_current_main"]
        changed = b"X" + raw[1:]
        self.assertEqual(probe.classify(changed, self.snap["contact"]),
                         "unreviewed_or_unavailable")

    def test_empty_and_oversized_public_bytes_fail_closed(self):
        for raw in (b"", b"X" * (probe.MAX_HTML + 1)):
            self.assertEqual(probe.classify(raw, self.snap["home"]),
                             "unreviewed_or_unavailable")

    def test_wrong_page_payload_never_cross_authorizes(self):
        raw = self.snap["contact"]["approved_plan1_source"]
        self.assertEqual(probe.classify(raw, self.snap["home"]),
                         "unreviewed_or_unavailable")

    def test_two_gets_can_prove_only_static_byte_identity(self):
        replies = {
            probe.URLS[0][1]: (200, self.snap["home"]["known_current_main"]),
            probe.URLS[1][1]: (200, self.snap["contact"]["known_current_main"]),
        }
        r = probe.inspect(lambda url: replies[url], self.snap)
        self.assertTrue(r["both_live_pages_exact_known_source"])
        self.assertEqual(r["pages"]["home"]["status"], 200)
        self.assertFalse(r["paid_challenge_available"])
        self.assertFalse(r["live_consent_or_receipt_verified"])
        self.assertTrue(r["no_post_no_customer_data_no_payment_no_release"])

    def test_http_200_html_body_can_still_be_unknown(self):
        replies = {
            probe.URLS[0][1]: (200, b"<html>UNKNOWN OWNER CONTENT</html>"),
            probe.URLS[1][1]: (200, self.snap["contact"]["known_current_main"]),
        }
        report = probe.inspect(lambda url: replies[url], self.snap)
        self.assertFalse(report["both_live_pages_exact_known_source"])
        self.assertEqual(report["pages"]["home"]["source_class"],
                         "unreviewed_or_unavailable")

    def test_http_404_and_missing_network_fail_closed(self):
        report = probe.inspect(
            lambda url: (404, b"") if "contact" in url
                        else (0, b""), self.snap
        )
        self.assertFalse(report["both_live_pages_exact_known_source"])
        self.assertEqual(report["pages"]["contact"]["status"], 404)

    def test_fixed_https_allowlist_rejects_external_candidate(self):
        with self.assertRaises(ValueError):
            probe._get("https://untrusted.example/collect")

    def test_pinned_source_drift_rejected_even_before_network(self):
        with patch.object(probe, "GIT_HOME_BLOB", "0" * 40):
            with self.assertRaises(ValueError):
                probe.allowed_snapshots()

    def test_no_post_no_redirect_without_cookies_or_secrets(self):
        from pathlib import Path
        source = Path(probe.__file__).read_text("utf-8")
        self.assertIn("method=\"GET\"", source)
        self.assertIn("return None", source)
        self.assertNotIn("method=\"POST\"", source)
        self.assertNotIn("HTTP_COOKIE", source)
        self.assertNotIn("os.environ", source)


if __name__ == "__main__":
    unittest.main()
