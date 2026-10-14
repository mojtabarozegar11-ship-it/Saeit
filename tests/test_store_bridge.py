"""Private VPS->cPanel handoff: integrity, idempotency, zero publication."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1] / "scripts"

def load(name):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

receiver = load("store_receiver")
sender = load("factory_store_sender")


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inbox = self.root / "private-inbox"
        self.product = self.root / "factory" / "farm_enterprise_economics"
        self.product.mkdir(parents=True)
        self.archive = self.product / "farm_enterprise_economics-internal-qa.zip"
        with zipfile.ZipFile(str(self.archive), "w", compression=zipfile.ZIP_DEFLATED) as f:
            f.writestr("farm_enterprise_economics/calculator.py", "print(42)")
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.meta = {
            "recipe": "farm_enterprise_economics",
            "artifact_sha256": self.digest,
            "qa_status": "passed",
            "commercial_status": "private_internal_qa_pass_not_published",
            "public_listing_enabled": False,
            "owner_publication_approval": False,
            "price": None,
        }
        self.manifest = self.product / "manufacturing_manifest.json"
        self.manifest.write_text(json.dumps(self.meta), encoding="utf-8")

    def stage(self):
        d = self.inbox / "incoming" / self.product.name
        d.mkdir(parents=True)
        (d / (self.digest + ".zip.partial")).write_bytes(self.archive.read_bytes())
        (d / (self.digest + ".json.partial")).write_bytes(self.manifest.read_bytes())

    def test_receipt_is_private_and_noncommercial(self):
        self.stage()
        receiver.finalize(self.inbox, self.product.name, self.digest)
        self.assertTrue(receiver.status(self.inbox, self.product.name, self.digest))
        receipt = json.loads(receiver.receipt_path(self.inbox, self.product.name, self.digest).read_text())
        self.assertFalse(receipt["public_store_listing"])
        self.assertFalse(receipt["database_written"])
        archive = self.inbox / "packages" / self.product.name / (self.digest + ".zip")
        self.assertEqual(archive.stat().st_mode & 0o777, 0o600)

    def test_tampered_archive_rejected(self):
        self.stage()
        path = self.inbox / "incoming" / self.product.name / (self.digest + ".zip.partial")
        path.write_bytes(b"corrupted")
        with self.assertRaises(ValueError):
            receiver.finalize(self.inbox, self.product.name, self.digest)

    def test_public_listing_flag_rejected(self):
        self.meta["public_listing_enabled"] = True
        self.manifest.write_text(json.dumps(self.meta))
        with self.assertRaises(ValueError):
            sender.verify_source(self.manifest, self.archive, self.product.name)
        self.stage()
        with self.assertRaises(ValueError):
            receiver.finalize(self.inbox, self.product.name, self.digest)

    def test_zip_path_traversal_rejected(self):
        with zipfile.ZipFile(str(self.archive), "w") as z:
            z.writestr("farm_enterprise_economics/../../escape.py", "unsafe")
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.meta["artifact_sha256"] = self.digest
        self.manifest.write_text(json.dumps(self.meta))
        self.stage()
        with self.assertRaises(ValueError):
            receiver.finalize(self.inbox, self.product.name, self.digest)

    def test_sender_does_not_contact_network_on_dry_run(self):
        with mock.patch.object(sender, "call", side_effect=AssertionError("no network allowed")):
            result = sender.deliver(self.product.name, self.product.parent, ["key"], dry_run=True)
        self.assertEqual(result["status"], "dry_run_private_only")

    def test_sender_skips_already_received(self):
        with mock.patch.object(sender, "call") as call:
            call.return_value = mock.Mock(returncode=0, stdout="STORE_PRIVATE_RECEIPT_VERIFIED")
            result = sender.deliver(self.product.name, self.product.parent, ["key"])
        self.assertEqual(result["status"], "already_received")
        self.assertEqual(call.call_count, 1)


if __name__ == "__main__":
    unittest.main()
