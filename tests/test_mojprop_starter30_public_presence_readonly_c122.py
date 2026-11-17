"""C122 fixed owner public Starter30 inventory, no site writes or customer requests."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import mojprop_starter30_public_presence_readonly_c122 as mod


class Starter30PublicStaticOwnerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.docroot = self.home / "mojplaywin.com"
        self.base = self.docroot / "moj-prop"
        self.starter = self.base / "starter-30-trx"
        self.starter.mkdir(parents=True)
        self.files = {
            "index.html": b"MOJPROP-STARTER30 reviewed educational index",
            "journal-template.csv": b"session,equity\n1,100.00\n",
            "journal-guide.txt": b"Reviewed educational guide, payment disabled",
        }
        self.pins = {name: mod.git_blob_sha(data) for name, data in self.files.items()}
        self.scope = [
            patch.object(mod, "HOME", self.home),
            patch.object(mod, "DOCROOT", self.docroot),
            patch.object(mod, "STATIC_DIR", self.starter),
        ]
        for p in self.scope:
            p.start()
            self.addCleanup(p.stop)

    def _write(self):
        for name, data in self.files.items():
            target = self.starter / name
            target.write_bytes(data)
            target.chmod(0o600)

    def _inspect(self):
        with patch.object(mod.pwd, "getpwuid",
                          return_value=SimpleNamespace(pw_name="zomorod2")), \
             patch.object(mod, "REVIEWED_BLOBS", self.pins):
            return mod.inspect()

    def test_01_three_exact_reviewed_files_are_only_a_disk_presence_proof(self):
        self._write()
        report = self._inspect()
        self.assertTrue(report["owner_identity_verified"])
        self.assertEqual(set(report["assets"]), set(self.files))
        self.assertTrue(report["all_three_reviewed_files_present"])
        self.assertTrue(all(s == "reviewed_exact" for s in report["assets"].values()))
        self.assertFalse(report["http_public_delivery_proven"])
        self.assertFalse(report["trx_payment_collected"])
        self.assertFalse(report["funded_prop_challenge_available"])

    def test_02_one_modified_file_invalidates_completeness(self):
        self._write()
        file = self.starter / "index.html"
        file.write_bytes(file.read_bytes() + b"<!-- changed -->")
        result = self._inspect()
        self.assertEqual(result["assets"]["index.html"], "unreviewed_bytes")
        self.assertFalse(result["all_three_reviewed_files_present"])

    def test_03_all_missing_files_are_marked_missing_not_unknown(self):
        result = self._inspect()
        self.assertEqual(set(result["assets"].values()), {"missing"})
        self.assertFalse(result["all_three_reviewed_files_present"])

    def test_04_missing_starter_directory_is_not_a_suspicious_symlink(self):
        self.starter.rmdir()
        result = self._inspect()
        self.assertEqual(set(result["assets"].values()), {"missing"})

    def test_05_symlinked_public_asset_never_followed(self):
        self._write()
        file = self.starter / "index.html"
        real = self.starter / "approved"
        file.rename(real)
        file.symlink_to(real)
        out = self._inspect()
        self.assertEqual(out["assets"]["index.html"], "unsafe")
        self.assertFalse(out["all_three_reviewed_files_present"])

    def test_06_symlinked_parent_directory_never_followed(self):
        self._write()
        original = self.base / "actual-source"
        self.starter.rename(original)
        self.starter.symlink_to(original, target_is_directory=True)
        out = self._inspect()
        self.assertEqual(set(out["assets"].values()), {"unsafe"})

    def test_07_hardlinked_file_has_untrusted_link_count(self):
        self._write()
        os.link(self.starter / "index.html", self.starter / "alias")
        out = self._inspect()
        self.assertEqual(out["assets"]["index.html"], "unsafe")

    def test_08_group_writable_file_is_never_called_reviewed(self):
        self._write()
        (self.starter / "index.html").chmod(0o660)
        out = self._inspect()
        self.assertEqual(out["assets"]["index.html"], "unsafe")

    def test_09_wrong_owner_process_exits_before_any_file_inventory(self):
        self._write()
        with patch.object(mod.pwd, "getpwuid",
                          return_value=SimpleNamespace(pw_name="not-owner")), \
             patch.object(mod, "inventory_one") as scanner:
            out = mod.inspect()
        scanner.assert_not_called()
        self.assertFalse(out["owner_identity_verified"])

    def test_10_manual_contact_route_source_file_is_metadata_only(self):
        self._write()
        contact = self.base / "contact"
        contact.mkdir()
        html = contact / "index.html"
        html.write_text("No payment or funded offer. Contact support.")
        html.chmod(0o600)
        out = self._inspect()
        self.assertTrue(out["contact_index_metadata_present"])
        self.assertFalse(out["http_public_delivery_proven"])
        self.assertFalse(out["email_lead_received"])

    def test_11_no_leak_or_commercial_claim_from_mismatched_files(self):
        self._write()
        (self.starter / "index.html").write_text(
            "private+buyer@example.com; token=super-secret; send TRX now"
        )
        out = self._inspect()
        self.assertNotIn("buyer@", str(out))
        self.assertNotIn("super-secret", str(out))
        for key in ("database_accessed", "customer_data_accessed",
                    "trx_payment_collected", "funded_prop_challenge_available",
                    "production_deployment_authorized", "new_cost_incurred"):
            self.assertIs(out[key], False)

    def test_12_exact_source_reviewed_blobs_have_not_been_fabricated(self):
        root = Path(__file__).resolve().parents[1] / "templates/moj-prop-v4/starter-30-trx"
        for name, expected in {
            "index.html": "c4185051020aa66405da8a9d8aaae3b22b90f7f6",
            "journal-template.csv": "2d732321f1c1f431685e514789cf26bf2a977d84",
            "journal-guide.txt": "7a8978ca6f3db31064552a41b2bdfb6c7de56036",
        }.items():
            with self.subTest(name=name):
                self.assertEqual(mod.git_blob_sha((root / name).read_bytes()), expected)
