"""Pure synthetic regression: buyer terms are not certified by a green CI."""
from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

from scripts import mojprop_plan1_buyer_terms_release_gate as g

REPO = Path(__file__).resolve().parents[1]
LIVE_CANDIDATE = REPO / "templates/moj-prop-plan1-sidecar/index.html"


def candidate() -> bytes:
    return (
        '<!doctype html><html lang="en"><main>'
        '<h1>Draft proposal v1.4.1</h1>'
        '<p>Not open for paid enrollment</p>'
        '<section id="fa" lang="fa" dir="rtl">'
        '<h2>نسخه v1.4.1</h2><p>فروش و پرداخت فعال نیست</p>'
        '</section></main></html>'
    ).encode("utf-8")


def assess(content: bytes, version: str = "v1.4.1", digest: str | None = None):
    return g.evaluate(
        content, version, hashlib.sha256(content).hexdigest()
        if digest is None else digest
    )


class BuyerTermsReleaseGate(unittest.TestCase):
    def test_01_future_pure_local_copy_parity_only(self):
        result = assess(candidate())
        self.assertTrue(result["copy_parity_passed"])
        self.assertFalse(result["independent_legal_approval_proven_by_this_tool"])
        self.assertFalse(result["independent_restore_proven_by_this_tool"])
        self.assertFalse(result["payment_enabled"])

    def test_02_real_current_sidecar_is_unapproved_stale(self):
        result = assess(LIVE_CANDIDATE.read_bytes())
        self.assertFalse(result["copy_parity_passed"])
        self.assertIn("english_persian_revision_mismatch", result["reasons"])
        self.assertIn("unresolved_buyer_terms", result["reasons"])

    def test_03_old_version_rejected_even_with_matching_hash(self):
        result = assess(candidate().replace(b"v1.4.1", b"v1.3"), "v1.3")
        self.assertIn("unapproved_or_obsolete_revision", result["reasons"])

    def test_04_missing_version_denied(self):
        self.assertIn("unapproved_or_obsolete_revision", assess(candidate(), "")["reasons"])

    def test_05_overlarge_version_denied(self):
        self.assertIsNone(g.revision("v1.4.1.999"))

    def test_06_version_semver_comparison(self):
        self.assertEqual(g.revision("v1.12.0"), (1, 12, 0))
        self.assertIsNone(g.revision("latest"))

    def test_07_wrong_approved_sha_denied(self):
        self.assertIn("reviewed_copy_byte_mismatch",
                      assess(candidate(), digest="a" * 64)["reasons"])

    def test_08_missing_sha_denied(self):
        self.assertIn("missing_exact_approved_copy_sha256",
                      assess(candidate(), digest="")["reasons"])

    def test_09_uppercase_sha_denied(self):
        self.assertIn("missing_exact_approved_copy_sha256",
                      assess(candidate(), digest="A" * 64)["reasons"])

    def test_10_one_byte_mutation_denied(self):
        a = candidate()
        b = a.replace(b"v1.4.1", b"v1.4.2")
        self.assertIn("reviewed_copy_byte_mismatch",
                      assess(b, "v1.4.2", hashlib.sha256(a).hexdigest())["reasons"])

    def test_11_missing_fa_section_denied(self):
        a = candidate().replace(b'id="fa"', b'id="farsi"')
        self.assertIn("missing_persian_section", assess(a)["reasons"])

    def test_12_missing_fa_version_denied(self):
        a = candidate().replace(b'\xd9\x86\xd8\xb3\xd8\xae\xd9\x87 v1.4.1',
                                b'\xd9\x86\xd8\xb3\xd8\xae\xd9\x87')
        self.assertIn("english_persian_revision_mismatch", assess(a)["reasons"])

    def test_13_missing_en_version_denied(self):
        a = candidate().replace(b"Draft proposal v1.4.1", b"Draft proposal")
        self.assertIn("english_persian_revision_mismatch", assess(a)["reasons"])

    def test_14_missing_english_no_charge_disclosure(self):
        a = candidate().replace(b"Not open for paid enrollment", b"Open")
        self.assertIn("nonpayable_disclosure_missing", assess(a)["reasons"])

    def test_15_missing_persian_no_charge_disclosure(self):
        a = candidate().replace("فروش و پرداخت فعال نیست".encode("utf-8"), b"")
        self.assertIn("nonpayable_disclosure_missing", assess(a)["reasons"])

    def test_16_form_denied(self):
        a = candidate().replace(b"</main>", b'<form action="/"></form></main>')
        self.assertIn("interactive_form_script_or_checkout", assess(a)["reasons"])

    def test_17_checkout_href_denied(self):
        a = candidate().replace(b"</main>", b'<a href="/checkout/">Pay</a></main>')
        self.assertIn("interactive_form_script_or_checkout", assess(a)["reasons"])

    def test_18_script_denied(self):
        a = candidate().replace(b"</main>", b"<script>alert(1)</script></main>")
        self.assertIn("interactive_form_script_or_checkout", assess(a)["reasons"])

    def test_19_valid_json_ld_is_permitted(self):
        a = candidate().replace(b"</main>", b'<script type="application/ld+json">{}</script></main>')
        self.assertTrue(assess(a)["copy_parity_passed"])

    def test_20_pending_social_clause_denied(self):
        a = candidate().replace(b"</main>",
             b"<p>Social-post conditions are under contract review</p></main>")
        self.assertIn("unresolved_buyer_terms", assess(a)["reasons"])

    def test_21_invalid_utf8_denied(self):
        self.assertIn("source_not_utf8", assess(candidate() + b"\xff")["reasons"])

    def test_22_empty_source_denied(self):
        self.assertIn("untrusted_source_size", assess(b"")["reasons"])

    def test_23_oversized_source_denied(self):
        self.assertIn("untrusted_source_size", assess(candidate() + b"a" * 131073)["reasons"])

    def test_24_no_external_approval_claims_even_if_copy_matches(self):
        result = assess(candidate())
        self.assertEqual(result["schema"], "mojprop.plan1.buyer_terms.release_parity.v1")
        self.assertFalse(result["independent_legal_approval_proven_by_this_tool"])
        self.assertFalse(result["payment_enabled"])


if __name__ == "__main__":
    unittest.main()
