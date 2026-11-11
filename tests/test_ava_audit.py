"""Integrity, cross-owner and lifecycle regression for the AVA code audit."""

from pathlib import Path
import os
import sqlite3
import stat
import tempfile
import unittest

from ava_core import (
    AuditIntegrityError, AuditKeyError, AvaRuntime, CheckEvidence,
    CodeEdit, CodeProposal, IsolatedReviewRunner, SQLiteCodeAuditTrail,
)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "review-audit.sqlite3"
        self.key = b"a" * 32
        self.review_id = "1" * 64
        self.evidence = "2" * 64

    def open_log(self, key=None):
        return SQLiteCodeAuditTrail(self.path, key=self.key if key is None else key)

    def test_append_reopen_and_verify_head(self):
        with self.open_log() as trail:
            first = trail.append("owner", self.review_id, "review_staged", self.evidence)
            second = trail.append("owner", self.review_id, "review_evaluated_pass", self.evidence)
            self.assertEqual(first.sequence, 1)
            self.assertEqual(second.sequence, 2)
            self.assertEqual(second.previous_mac, first.mac)
            self.assertEqual(trail.verify("owner").head_mac, second.mac)
        with self.open_log() as trail:
            self.assertEqual(trail.verify("owner").event_count, 2)
            self.assertEqual(trail.history("owner")[1].kind, "review_evaluated_pass")

    def test_owner_isolation_and_pseudonymous_storage(self):
        with self.open_log() as trail:
            trail.append("private-owner-name", self.review_id, "review_staged", self.evidence)
            trail.append("other", "3" * 64, "review_staged", "4" * 64)
            self.assertEqual(trail.verify("private-owner-name").event_count, 1)
            self.assertEqual(trail.verify("other").event_count, 1)
            self.assertEqual(trail.verify("unknown").event_count, 0)
        self.assertNotIn(b"private-owner-name", self.path.read_bytes())

    def test_wrong_secret_denied_even_after_reopen(self):
        with self.open_log() as trail:
            trail.append("owner", self.review_id, "review_staged", self.evidence)
        with self.assertRaises(AuditKeyError):
            self.open_log(key=b"b" * 32)

    def test_missing_key_verifier_with_head_detected(self):
        with self.open_log() as trail:
            trail.append("owner", self.review_id, "review_staged", self.evidence)
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM audit_key")
            db.execute("DELETE FROM audit_events")
        with self.assertRaises(AuditKeyError):
            self.open_log()

    def test_created_database_has_private_mode(self):
        with self.open_log():
            self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_world_readable_database_denied(self):
        self.path.touch(mode=0o600)
        os.chmod(self.path, 0o644)
        with self.assertRaises(PermissionError):
            self.open_log()

    def test_symlink_path_denied(self):
        original = Path(self.directory.name) / "original.db"
        original.touch()
        self.path.symlink_to(original)
        with self.assertRaises(PermissionError):
            self.open_log()

    def test_tampered_event_kind_caught_by_chain_verifier(self):
        with self.open_log() as trail:
            trail.append("owner", self.review_id, "review_staged", self.evidence)
            with sqlite3.connect(self.path) as db:
                db.execute("UPDATE audit_events SET kind='handoff_approved'")
            with self.assertRaises(AuditIntegrityError):
                trail.verify("owner")

    def test_tampered_event_evidence_detected(self):
        with self.open_log() as trail:
            trail.append("owner", self.review_id, "review_staged", self.evidence)
            with sqlite3.connect(self.path) as db:
                db.execute("UPDATE audit_events SET evidence_sha256=?", ("f" * 64,))
            with self.assertRaises(AuditIntegrityError):
                trail.history("owner")

    def test_deleted_tail_detected_using_owner_head(self):
        with self.open_log() as trail:
            trail.append("owner", self.review_id, "review_staged", self.evidence)
            trail.append("owner", self.review_id, "review_evaluated_pass", self.evidence)
            with sqlite3.connect(self.path) as db:
                db.execute("DELETE FROM audit_events WHERE seq=2")
            with self.assertRaises(AuditIntegrityError):
                trail.verify("owner")

    def test_missing_head_detected(self):
        with self.open_log() as trail:
            trail.append("owner", self.review_id, "review_staged", self.evidence)
            with sqlite3.connect(self.path) as db:
                db.execute("DELETE FROM audit_heads")
            with self.assertRaises(AuditIntegrityError):
                trail.verify("owner")

    def test_no_further_writes_after_corrupt_chain(self):
        with self.open_log() as trail:
            trail.append("owner", self.review_id, "review_staged", self.evidence)
            with sqlite3.connect(self.path) as db:
                db.execute("UPDATE audit_events SET previous_mac='wrong'")
            with self.assertRaises(AuditIntegrityError):
                trail.append("owner", self.review_id, "review_evaluated_pass", self.evidence)

    def test_invalid_event_digest_or_kind_rejected(self):
        with self.open_log() as trail:
            for review, kind, evidence in (
                ("short", "review_staged", self.evidence),
                (self.review_id, "unknown", self.evidence),
                (self.review_id, "review_staged", "short"),
            ):
                with self.subTest(kind=kind, evidence=evidence), self.assertRaises(ValueError):
                    trail.append("owner", review, kind, evidence)
            self.assertEqual(trail.verify("owner").event_count, 0)

    def test_runtime_records_staging_once_and_rollback_event(self):
        with self.open_log() as trail:
            runtime = AvaRuntime(
                owner_id="owner", brain=lambda _: "hi", propose_goals=lambda _: (),
                code_audit=trail,
            )
            old = "value=1\n"
            new = "value=2\n"
            proposal = CodeProposal(
                goal="Improve internal code", rationale="Small fix",
                edits=(CodeEdit("ava_core/example.py", runtime.evolution.digest(old), new),),
            )
            review = runtime.review_code_change(proposal, trusted_files={"ava_core/example.py": old})
            runtime.review_code_change(proposal, trusted_files={"ava_core/example.py": old})
            self.assertEqual(runtime.status().code_audit_events, 1)
            plan = runtime.prepare_code_rollback(
                review.review_id,
                trusted_before={"ava_core/example.py": old},
                trusted_current={"ava_core/example.py": new},
            )
            self.assertEqual(plan.files[0].action, "restore")
            self.assertEqual(runtime.status().code_audit_events, 2)
            self.assertEqual(trail.history("owner")[-1].kind, "rollback_prepared")

    def test_runtime_rejects_forged_external_evidence(self):
        with self.open_log() as trail:
            runtime = AvaRuntime(owner_id="owner", brain=lambda _: "hi",
                                 propose_goals=lambda _: (), code_audit=trail)
            proposal = CodeProposal(
                goal="Improve internal code", rationale="Small fix",
                edits=(CodeEdit("ava_core/example.py", None, "value=2\n"),),
            )
            review = runtime.review_code_change(proposal, trusted_files={})
            fake = CheckEvidence(review.review_id, True, True, 100, "claimed", "unverified")
            with self.assertRaises(PermissionError):
                runtime.approve_code_handoff(review.review_id, evidence=fake,
                                             authorize=lambda *_: True)
            self.assertEqual(trail.verify("owner").event_count, 1)

    def test_runtime_denies_evaluation_of_unlogged_review(self):
        with self.open_log() as trail:
            runtime = AvaRuntime(
                owner_id="owner", brain=lambda _: "hi", propose_goals=lambda _: (),
                review_runner=IsolatedReviewRunner(owner_id="owner"), code_audit=trail,
            )
            review = runtime.evolution.stage(
                CodeProposal("Improve code", "Small fix", (
                    CodeEdit("ava_core/example.py", None, "value=2\n"),
                )), trusted_files={},
            )
            with self.assertRaises(PermissionError):
                runtime.evaluate_code_change(review.review_id, trusted_tree={})

    def test_runtime_records_actual_isolated_evaluation_and_handoff(self):
        with self.open_log() as trail:
            runner = IsolatedReviewRunner(owner_id="owner", timeout_seconds=5)
            runtime = AvaRuntime(
                owner_id="owner", brain=lambda _: "hi", propose_goals=lambda _: (),
                review_runner=runner, code_audit=trail,
            )
            old, new = "value=1\n", "value=2\n"
            suite = (
                "import unittest\nfrom ava_core.example import value\n"
                "class Check(unittest.TestCase):\n"
                "    def test_updated(self):\n        self.assertEqual(value, 2)\n"
            )
            review = runtime.review_code_change(
                CodeProposal("Improve internal code", "Small fix", (
                    CodeEdit("ava_core/example.py", runtime.evolution.digest(old), new),
                )), trusted_files={"ava_core/example.py": old},
            )
            result = runtime.evaluate_code_change(review.review_id, trusted_tree={
                "ava_core/__init__.py": "", "ava_core/example.py": old,
                "tests/test_ava_example.py": suite,
            })
            self.assertTrue(result.evidence.passed, result.stderr_excerpt)
            bundle = runtime.approve_code_handoff(
                review.review_id, evidence=result.evidence, authorize=lambda *_: True,
            )
            self.assertEqual(bundle.review.review_id, review.review_id)
            self.assertEqual(
                [entry.kind for entry in trail.history("owner")],
                ["review_staged", "review_evaluated_pass", "handoff_approved"],
            )


if __name__ == "__main__":
    unittest.main()
