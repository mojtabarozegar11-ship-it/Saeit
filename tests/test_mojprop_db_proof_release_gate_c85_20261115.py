"""Offline fail-closed verification that real MariaDB restore evidence gates release.

Tests patch the read-only DB fingerprint; they never connect to a server,
modify a database, create production payment or assert a genuine restore.
"""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts import deploy_mojplaywin_moj_prop_backend as backend


RUN = "850001"
COMMIT = "a" * 40
IDENTITY = "b" * 64
KEY = "standalone-private-rehearsal-reviewer-key-over-32-characters"


class IndependentRestoreReleaseGateTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.temp = Path(t.name)
        self.live = self.temp / "live"
        self.live.mkdir()
        self.staged = self.temp / "staged"
        script = self.staged / "scripts/mojprop_live_database_identity_c85.py"
        script.parent.mkdir(parents=True)
        script.write_text("# strictly synthetic fixture\n")
        self.private = self.temp / "private"
        self.private.mkdir()
        for name, value in (
            ("ROOT", self.live),
            ("INDEPENDENT_DB_EVIDENCE_ROOT", self.private),
        ):
            p = patch.object(backend, name, value)
            p.start()
            self.addCleanup(p.stop)

    def check(self):
        return backend.require_independent_db_restore(RUN, COMMIT, self.staged)

    def test_missing_independent_key_and_proof_path_denied_before_connection(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(backend, "choose_python") as python:
                with self.assertRaisesRegex(RuntimeError, "independent DB restore"):
                    self.check()
                python.assert_not_called()

    def test_wrong_private_evidence_root_fails_before_connection(self):
        with patch.dict(os.environ, {
            "MOJPROP_INDEPENDENT_RESTORE_VERIFIER_KEY": KEY,
            "MOJPROP_PRIVATE_DB_RESTORE_ROOT": "/tmp/unauthorized",
        }):
            with patch.object(backend, "choose_python") as python:
                with self.assertRaisesRegex(RuntimeError, "independent DB restore"):
                    self.check()
                python.assert_not_called()

    def test_signed_proof_requires_actual_read_only_connected_db_identity(self):
        with patch.dict(os.environ, {
            "MOJPROP_INDEPENDENT_RESTORE_VERIFIER_KEY": KEY,
            "MOJPROP_PRIVATE_DB_RESTORE_ROOT": str(self.private),
        }):
            with patch.object(backend, "choose_python", return_value=Path("/fake/venv/python")):
                with patch.object(backend.subprocess, "run", return_value=types.SimpleNamespace(
                    returncode=0, stdout=IDENTITY + "\n"
                )) as connected:
                    with patch.object(backend, "verify_database_restore_evidence",
                                      return_value={"rehearsal_receipt_verified": True}) as proof:
                        with contextlib.redirect_stdout(io.StringIO()):
                            result = self.check()
                        self.assertTrue(result["rehearsal_receipt_verified"])
                        args = connected.call_args.args[0]
                        self.assertEqual(args[1], str(self.staged / "scripts/mojprop_live_database_identity_c85.py"))
                        self.assertEqual(proof.call_args.kwargs["database_identity_sha256"], IDENTITY)
                        self.assertEqual(proof.call_args.kwargs["source_commit"], COMMIT)
                        self.assertEqual(proof.call_args.kwargs["run_id"], RUN)
                        self.assertEqual(proof.call_args.kwargs["root"], self.private)

    def test_connection_failure_prevents_claiming_signed_evidence(self):
        with patch.dict(os.environ, {
            "MOJPROP_INDEPENDENT_RESTORE_VERIFIER_KEY": KEY,
            "MOJPROP_PRIVATE_DB_RESTORE_ROOT": str(self.private),
        }):
            with patch.object(backend, "choose_python", return_value=Path("/fake/runtime")):
                with patch.object(backend.subprocess, "run", return_value=types.SimpleNamespace(
                    returncode=1, stdout=""
                )):
                    with patch.object(backend, "verify_database_restore_evidence") as evidence:
                        with self.assertRaisesRegex(RuntimeError, "connected MariaDB"):
                            self.check()
                        evidence.assert_not_called()

    def test_valid_identity_without_independent_signature_is_not_approval(self):
        with patch.dict(os.environ, {
            "MOJPROP_INDEPENDENT_RESTORE_VERIFIER_KEY": KEY,
            "MOJPROP_PRIVATE_DB_RESTORE_ROOT": str(self.private),
        }):
            with patch.object(backend, "choose_python", return_value=Path("/fake/runtime")):
                with patch.object(backend.subprocess, "run", return_value=types.SimpleNamespace(
                    returncode=0, stdout=IDENTITY
                )):
                    with patch.object(backend, "verify_database_restore_evidence",
                                      return_value={"rehearsal_receipt_verified": False}):
                        with self.assertRaisesRegex(RuntimeError, "not verified"):
                            self.check()

    def test_gate_is_before_backup_or_schema_write(self):
        source = Path(backend.__file__).read_text(encoding="utf-8")
        deployment = source.split("\ndef deploy(", 1)[1]
        self.assertLess(
            deployment.index("require_independent_db_restore(run_id, commit, staged_root)"),
            deployment.index("backup.mkdir(parents=True"),
        )
        self.assertLess(
            deployment.index("require_independent_db_restore(run_id, commit, staged_root)"),
            deployment.index('run_checked([str(python), "manage.py", "migrate"'),
        )

    def test_manual_workflow_checks_proof_before_publishing_catalog(self):
        workflow = Path(__file__).resolve().parents[1] / (
            ".github/workflows/mojprop-backend-controlled-release-20261115.yml"
        )
        text = workflow.read_text(encoding="utf-8")
        self.assertIn("  workflow_dispatch:\n", text)
        self.assertNotIn("  push:\n", text)
        self.assertIn("MOJPROP_BACKUP_RESTORE_VERIFIED", text)
        self.assertLess(
            text.index("- name: Require private independently signed MariaDB restore proof"),
            text.index("- name: Update only /moj-prop/ commercial catalog"),
        )
        self.assertIn("verify-db-restore $GITHUB_RUN_ID $GITHUB_SHA", text)

    def test_verification_never_creates_or_updates_real_customer_data(self):
        script = Path(__file__).resolve().parents[1] / (
            "scripts/mojprop_live_database_identity_c85.py"
        )
        source = script.read_text(encoding="utf-8")
        self.assertIn('cursor.execute("SELECT DATABASE()")', source)
        for forbidden in ("DELETE FROM ", "INSERT INTO ", "UPDATE core_", "CREATE TABLE "):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
