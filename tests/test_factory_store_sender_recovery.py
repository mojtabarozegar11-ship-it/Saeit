"""A failed private product QA must not starve healthy factory delivery.

No network requests, customer payments, or public store activation.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile


SOURCE = Path(__file__).resolve().parents[1] / "scripts/factory_store_sender.py"
SPEC = importlib.util.spec_from_file_location("factory_store_sender_isolation", SOURCE)
sender = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sender)


def product(directory, recipe, *, good=True):
    target = directory / recipe
    target.mkdir()
    archive = target / (recipe + "-internal-qa.zip")
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("package/README.txt", "A tested private archive")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (target / "manufacturing_manifest.json").write_text(json.dumps({
        "recipe": recipe,
        "artifact_sha256": digest if good else "0" * 64,
        "qa_status": "passed",
        "commercial_status": "private_internal_qa_pass_not_published",
        "owner_publication_approval": False,
        "public_listing_enabled": False,
        "price": None,
    }), encoding="utf-8")


class FactoryPrivateQAFailureIsolation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "private" / "digital-products"
        self.root.mkdir(parents=True)

    def test_bad_first_package_does_not_stop_three_good_packages(self):
        product(self.root, "alpha", good=False)
        for recipe in ("bravo", "charlie", "delta"):
            product(self.root, recipe)
        calls = []
        def fake_deliver(recipe, root, options, *, dry_run=False):
            calls.append(recipe)
            return {"recipe": recipe, "status": "received_private"}
        with mock.patch.object(sender, "host_ssh_options", return_value=[]), \
             mock.patch.object(sender, "deliver", side_effect=fake_deliver):
            results = sender.sync(self.root, "unused", "unused", limit=3)
        self.assertEqual([r["status"] for r in results],
                         ["blocked_private_qa", "received_private",
                          "received_private", "received_private"])
        self.assertEqual(calls, ["bravo", "charlie", "delta"])
        self.assertEqual(sender.read_cursor(self.root.parent / "store-send-cursor.json"),
                         "delta")

    def test_bad_only_does_not_advance_cursor_or_claim_transfer(self):
        product(self.root, "alpha", good=False)
        with mock.patch.object(sender, "host_ssh_options", return_value=[]), \
             mock.patch.object(sender, "deliver") as transfer:
            result = sender.sync(self.root, "unused", "unused", limit=3)
        self.assertEqual(result[0]["status"], "blocked_private_qa")
        transfer.assert_not_called()
        self.assertFalse((self.root.parent / "store-send-cursor.json").exists())

    def test_remote_receipt_error_remains_hard_failure(self):
        product(self.root, "alpha")
        with mock.patch.object(sender, "host_ssh_options", return_value=[]), \
             mock.patch.object(sender, "deliver", side_effect=RuntimeError("RECEIPT_FAILED")):
            with self.assertRaisesRegex(RuntimeError, "RECEIPT_FAILED"):
                sender.sync(self.root, "unused", "unused", limit=3)
        self.assertFalse((self.root.parent / "store-send-cursor.json").exists())

    def test_dry_run_never_claims_real_transfer(self):
        result = [
            {"recipe": "alpha", "status": "blocked_private_qa"},
            {"recipe": "bravo", "status": "dry_run_private_only"},
        ]
        buf = io.StringIO()
        with mock.patch.object(sender, "sync", return_value=result), \
             contextlib.redirect_stdout(buf):
            rc = sender.main(["--products", str(self.root),
                              "--ssh-key", "unused", "--known-hosts", "unused",
                              "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("FACTORY_STORE_TRANSFER_COUNT=0", buf.getvalue())
        self.assertIn("FACTORY_STORE_QA_BLOCKED_COUNT=1", buf.getvalue())
        self.assertIn("FACTORY_STORE_DRY_RUN_VERIFIED_COUNT=1", buf.getvalue())
        self.assertIn("FACTORY_STORE_PUBLIC_LISTING_ENABLED=false", buf.getvalue())

    def test_existing_receipt_is_not_a_new_transfer(self):
        result = [
            {"recipe": "alpha", "status": "already_received"},
            {"recipe": "bravo", "status": "received_private"},
        ]
        buf = io.StringIO()
        with mock.patch.object(sender, "sync", return_value=result), \
             contextlib.redirect_stdout(buf):
            sender.main(["--products", str(self.root),
                         "--ssh-key", "unused", "--known-hosts", "unused"])
        self.assertIn("FACTORY_STORE_TRANSFER_COUNT=1", buf.getvalue())
        self.assertIn("FACTORY_STORE_RECEIPT_VERIFIED_COUNT=2", buf.getvalue())
        self.assertIn("FACTORY_STORE_ALREADY_RECEIVED_COUNT=1", buf.getvalue())

    def test_consumer_provenance_rejects_invalid_or_nonobject_json(self):
        recipe, version = "alpha", "0" * 64
        product(self.root, recipe)
        directory = self.root.parent / "customer-packs" / recipe / version
        directory.mkdir(parents=True)
        (directory / "customer-package.zip").write_bytes(b"test private archive")
        candidate = directory / "candidate_manifest.json"
        source = self.root / recipe / "manufacturing_manifest.json"
        valid_source = source.read_text(encoding="utf-8")
        for raw in ("[]", "null", '"unexpected"', "123", "{"):
            with self.subTest(candidate=raw):
                source.write_text(valid_source, encoding="utf-8")
                candidate.write_text(raw, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "CONSUMER_MANIFEST_"):
                    sender.verify_consumer_source(self.root.parent, recipe, version)
        candidate.write_text('{"schema":"saeit.factory.consumer-package.v1"}',
                             encoding="utf-8")
        for raw in ("[]", "null", "{"):
            with self.subTest(source=raw):
                source.write_text(raw, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "CONSUMER_MANIFEST_"):
                    sender.verify_consumer_source(self.root.parent, recipe, version)

    def test_failed_remote_call_reports_safe_stage_not_ssh_credential(self):
        command = ["ssh", "-i", "synthetic-sensitive-private-key", "private-host"]
        with mock.patch.object(sender.subprocess, "run",
                               return_value=mock.Mock(returncode=255)):
            with self.assertRaisesRegex(RuntimeError,
                                        "PRIVATE_DELIVERY_STATUS_RC_255") as error:
                sender.call(command, allowed=(0, 1), stage="status")
        self.assertNotIn("synthetic-sensitive-private-key", str(error.exception))
        self.assertNotIn("private-host", str(error.exception))

    def test_unrecognized_error_stage_is_never_logged(self):
        with mock.patch.object(sender.subprocess, "run",
                               return_value=mock.Mock(returncode=3)):
            with self.assertRaisesRegex(RuntimeError,
                                        "PRIVATE_DELIVERY_UNKNOWN_RC_3") as error:
                sender.call(["ssh", "private-host"], stage="anything_secret")
        self.assertNotIn("anything_secret", str(error.exception))

    def test_install_workflow_retains_vps_sender_rollback(self):
        workflow = (SOURCE.parents[1] / ".github/workflows/vps-store-bridge-install.yml"
                    ).read_text(encoding="utf-8")
        for required in (
            'flock -w 45 9',
            'cp -p "$script" "$backup"',
            'trap rollback_sender EXIT',
            'PRIVATE_SENDER_ROLLBACK_RESTORED',
            'FACTORY_STORE_RECEIPT_VERIFIED_COUNT=',
            'PRIVATE_NO_RECEIPT_VERIFIED',
            'PRIVATE_CPANEL_RECEIVER_UPDATED_WITH_VERIFIED_BACKUP',
            'cp -p "$active" "$backup/receiver.before.py"',
            'cmp -s "$active" "$backup/receiver.before.py"',
            'python3 -m py_compile "$active"',
            'PRIVATE_CPANEL_RECEIVER_UNCHANGED',
        ):
            self.assertIn(required, workflow)


if __name__ == "__main__":
    unittest.main()
