"""Offline regressions for source-only attestations; no network or finance DB."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from zm_chatgpt_action_index import CREATE_SQL, SOURCE  # noqa: E402
from zm_chatgpt_evidence_verify import (  # noqa: E402
    classify_url, evaluate, github_json, run,
)


REPO_URL = "https://github.com/mojtabarozegar11-ship-it/Saeit/"
DIGEST = "a" * 64


def row(n, url, status="completed"):
    return (f"ZM05-0018-A{n:02d}", DIGEST, url, status)


class ReferenceClassificationTests(unittest.TestCase):
    def test_commit_exists_is_only_source_evidence(self):
        sha = "1" * 40
        self.assertEqual(classify_url(REPO_URL + "commit/" + sha,
                                      fetch=lambda path: {"sha": sha}), "source_exists")

    def test_green_ci_is_not_business_effect(self):
        url = REPO_URL + "actions/runs/12345"
        reply = {"id": 12345, "status": "completed", "conclusion": "success",
                 "repository": {"full_name": "mojtabarozegar11-ship-it/Saeit"}}
        self.assertEqual(classify_url(url, fetch=lambda _: reply), "ci_success")
        reply["repository"]["full_name"] = "attacker/other"
        self.assertEqual(classify_url(url, fetch=lambda _: reply), "mismatch")

    def test_draft_pr_cannot_be_counted_as_release(self):
        url = REPO_URL + "pull/1793"
        self.assertEqual(classify_url(url, fetch=lambda _: {"number": 1793, "merged": False,
                                                              "merged_at": None}), "proposal_only")

    def test_issues_and_invalid_urls_are_not_effect_proof(self):
        self.assertEqual(classify_url(REPO_URL + "issues/1725#issuecomment-123",
                                      fetch=lambda _: {"number": 1725}), "issue_exists")
        self.assertEqual(classify_url("https://evil.invalid/attest",
                                      fetch=lambda _: self.fail("unexpected request")), "invalid_reference")

    def test_missing_or_failed_ci_does_not_pass(self):
        url = REPO_URL + "actions/runs/22"
        self.assertEqual(classify_url(url, fetch=lambda _: None), "unavailable")
        self.assertEqual(classify_url(url, fetch=lambda _: {"id": 22, "status": "completed",
            "conclusion": "failure", "repository": {"full_name": "mojtabarozegar11-ship-it/Saeit"}}),
            "ci_not_successful")

    def test_api_path_is_fixed_not_caller_supplied(self):
        with self.assertRaises(ValueError):
            github_json("/../../other", opener=lambda *_a, **_k: None)

    def test_latest_completed_actions_get_priority(self):
        rows = [row(1, REPO_URL + "issues/1"), row(2, REPO_URL + "issues/2"),
                row(3, "", "blocked"), row(4, REPO_URL + "issues/4")]
        results, checked = evaluate(rows, limit=2, fetch=lambda path: {"number": int(path.rsplit("/", 1)[-1])})
        self.assertEqual(checked, 2)
        self.assertEqual([x["reference_status"] for x in results],
                         ["not_checked", "issue_exists", "not_checked", "issue_exists"])


class PrivateAttestationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.private = Path(self.tmp.name) / "private"
        self.private.mkdir(mode=0o700)
        self.index = self.private / "chatgpt_actions_index.sqlite3"
        self.output = self.private / "chatgpt_evidence_attestations.json"
        with sqlite3.connect(self.index) as db:
            db.executescript(CREATE_SQL)
            db.executemany("INSERT INTO metadata VALUES (?,?)",
                           [("source", SOURCE), ("verification", "not_checked")])
            db.execute("INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (1, "ZM05-0018-A01", "05-0018", 100, "2026-11-02T00:00:00Z",
                        "اصلاح مستند", "completed", "کد پیشنهادی", REPO_URL + "issues/1725", DIGEST))
        self.index.chmod(0o600)

    def test_preview_never_creates_attestation_or_changes_index(self):
        before = self.index.read_bytes()
        result = run(self.index, self.output, fetch=lambda _: {"number": 1725})
        self.assertEqual(result["references_checked"], 1)
        self.assertEqual(result["business_effect_verified"], 0)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.index.read_bytes(), before)

    def test_commit_requires_gate_and_stores_only_provenance(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "EVIDENCE_COMMIT_GATE_DISABLED"):
                run(self.index, self.output, commit=True, fetch=lambda _: {"number": 1725})
        with patch.dict(os.environ, {"ZM_ACTION_EVIDENCE_VERIFY_ENABLED": "1"}):
            run(self.index, self.output, commit=True, fetch=lambda _: {"number": 1725})
        saved = json.loads(self.output.read_text())
        self.assertFalse(saved["business_effect_verified"])
        self.assertEqual(saved["results"][0]["reference_status"], "issue_exists")
        self.assertEqual(self.output.stat().st_mode & 0o077, 0)

    def test_existing_record_cannot_be_rewritten(self):
        with patch.dict(os.environ, {"ZM_ACTION_EVIDENCE_VERIFY_ENABLED": "1"}):
            run(self.index, self.output, commit=True, fetch=lambda _: {"number": 1725})
            with sqlite3.connect(self.index) as db:
                db.execute("UPDATE actions SET receipt_sha256=?", ("b" * 64,))
            with self.assertRaisesRegex(ValueError, "IMMUTABLE_ATTESTATION_HISTORY_CHANGED"):
                run(self.index, self.output, commit=True, fetch=lambda _: {"number": 1725})

    def test_symlink_output_is_rejected_without_touching_target(self):
        target = self.private / "other.txt"
        target.write_text("untouched")
        self.output.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "UNSAFE_ACTION_PATH"):
            run(self.index, self.output, fetch=lambda _: {"number": 1725})
        self.assertEqual(target.read_text(), "untouched")

    def test_source_index_only_separate_financial_db(self):
        financial = self.private / "management.sqlite3"
        financial.write_bytes(b"DO NOT CHANGE")
        with patch.dict(os.environ, {"ZM_ACTION_EVIDENCE_VERIFY_ENABLED": "1"}):
            run(self.index, self.output, commit=True, fetch=lambda _: {"number": 1725})
        self.assertEqual(financial.read_bytes(), b"DO NOT CHANGE")


if __name__ == "__main__":
    unittest.main()
