"""Regression tests: no unsigned document can make a company 'verified'."""
import json
import unittest

from scripts.zomorod_legal_publication_gate_20261024 import assess


class LegalEvidenceIntakeTests(unittest.TestCase):
    def sample(self):
        digest = "a" * 64
        def entry(source):
            return {
                "source_url": source,
                "record_number": "sample-only",
                "issued_at": "2020-01-01",
                "checked_at": "2026-01-01",
                "sha256": digest,
            }
        return {
            "identity": {"legal_name": "Example Company", "national_id": "14008746024"},
            "evidence": {
                "national_identity": entry("https://ilenc.ssaa.ir/"),
                "incorporation_notice": entry("https://www.rrk.ir/News/NewsList.aspx"),
                "latest_changes": entry("https://www.rrk.ir/News/NewsList.aspx"),
            },
            "signing_authority_review": {
                "matched_to_latest_changes": True,
                "reviewed_at": "2026-01-01",
            },
            "public_disclosure_approval": {"approved": True},
            "secret_personal_id": "DO-NOT-LEAK",
        }

    def test_missing_records_remain_blocked(self):
        result = assess({})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("national_identity:missing", result["gaps"])
        self.assertFalse(result["publication_allowed"])

    def test_even_complete_metadata_is_only_review_candidate(self):
        result = assess(self.sample())
        self.assertEqual(result["status"], "REVIEW_CANDIDATE")
        self.assertEqual(result["gaps"], [])
        self.assertFalse(result["official_verification_granted"])
        self.assertFalse(result["publication_allowed"])
        self.assertNotIn("DO-NOT-LEAK", json.dumps(result))

    def test_secondary_and_non_https_sources_rejected(self):
        for url in ("https://linka.ir/company/example", "http://ilenc.ssaa.ir/",
                    "https://user:pass@ilenc.ssaa.ir/", "https://ilenc.ssaa.ir.evil.org/"):
            with self.subTest(url=url):
                sample = self.sample()
                sample["evidence"]["national_identity"]["source_url"] = url
                self.assertIn("national_identity:official_source_url", assess(sample)["gaps"])

    def test_missing_current_signer_review_remains_blocked(self):
        sample = self.sample()
        sample["signing_authority_review"]["matched_to_latest_changes"] = False
        self.assertIn("signing_authority:current_powers_not_matched", assess(sample)["gaps"])

    def test_no_privacy_approval_means_no_public_candidate(self):
        sample = self.sample()
        sample["public_disclosure_approval"]["approved"] = False
        self.assertEqual(assess(sample)["status"], "BLOCKED")
        self.assertIn("privacy:publication_approval_missing", assess(sample)["gaps"])

    def test_malformed_metadata_fails_closed(self):
        for malformed in (None, [], "text"):
            with self.subTest(malformed=malformed):
                self.assertEqual(assess(malformed)["status"], "BLOCKED")
        sample = self.sample()
        sample["evidence"]["latest_changes"]["source_url"] = ["not a URL"]
        sample["evidence"]["national_identity"]["sha256"] = []
        sample["evidence"]["incorporation_notice"]["issued_at"] = "9999-01-01"
        self.assertEqual(assess(sample)["status"], "BLOCKED")
        self.assertEqual(len([x for x in assess(sample)["gaps"] if x.endswith(("digest", "issue_date", "official_source_url"))]), 3)

    def test_unverified_approval_flags_do_not_override_missing_evidence(self):
        sample = self.sample()
        del sample["evidence"]["latest_changes"]
        sample["verified"] = True
        sample["publication_allowed"] = True
        result = assess(sample)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["publication_allowed"])
        self.assertFalse(result["official_verification_granted"])


if __name__ == "__main__":
    unittest.main()
