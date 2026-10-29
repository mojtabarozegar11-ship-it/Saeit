"""Free factory digital release: checksum, authorization, isolation and idempotence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


receiver = load("store_receiver")
publisher = load("publish_factory_free_tool")


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.inbox = self.base / ".saeit-factory-inbox"
        self.webroot = self.base / "mojplaywin.com"
        self.webroot.mkdir()
        recipe = publisher.RECIPE
        src = self.base / "source.zip"
        with zipfile.ZipFile(str(src), "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(recipe + "/calculator.py", "print('offline')")
        self.sha = hashlib.sha256(src.read_bytes()).hexdigest()
        path = self.inbox / "incoming" / recipe
        path.mkdir(parents=True)
        (path / (self.sha + ".zip.partial")).write_bytes(src.read_bytes())
        (path / (self.sha + ".json.partial")).write_text(json.dumps({
            "name": "Farm Enterprise Economics Toolkit",
            "recipe": recipe,
            "artifact_sha256": self.sha,
            "qa_status": "passed",
            "commercial_status": "private_internal_qa_pass_not_published",
            "price": None,
            "public_listing_enabled": False,
            "owner_publication_approval": False,
        }))
        receiver.finalize(self.inbox, recipe, self.sha)

    def test_authorization_is_required(self):
        with self.assertRaisesRegex(ValueError, "AUTHORIZATION_REQUIRED"):
            publisher.publish(self.inbox, self.webroot)
        self.assertFalse((self.webroot / "factory-releases").exists())

    def test_release_blocked_without_signed_rights_evidence(self):
        with self.assertRaisesRegex(ValueError, "RIGHTS_CLEARANCE_EVIDENCE_MISSING"):
            publisher.publish(self.inbox, self.webroot, release_authorized=True)
        self.assertFalse(
            (self.webroot / "factory-releases" / publisher.PUBLIC_SLUG).exists()
        )

    def test_existing_conflicting_public_directory_never_overwritten(self):
        dest = self.webroot / "factory-releases" / publisher.PUBLIC_SLUG
        dest.mkdir(parents=True)
        (dest / "index.html").write_text("existing customer-facing content")
        with self.assertRaisesRegex(ValueError, "REFUSING_TO_REPLACE"):
            publisher.publish(self.inbox, self.webroot, release_authorized=True)
        self.assertEqual((dest / "index.html").read_text(), "existing customer-facing content")

    def test_checksum_integrity_before_publication(self):
        artifact = self.inbox / "packages" / publisher.RECIPE / (self.sha + ".zip")
        artifact.write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            publisher.publish(self.inbox, self.webroot, release_authorized=True)
        self.assertFalse((self.webroot / "factory-releases").exists())

    def test_wrong_docroot_is_rejected(self):
        bad = self.base / "another_domain"
        bad.mkdir()
        with self.assertRaisesRegex(ValueError, "WRONG_STOREFRONT"):
            publisher.publish(self.inbox, bad, release_authorized=True)

    def test_preview_cannot_bypass_missing_signed_rights_clearance(self):
        dest = self.webroot / "factory-releases" / publisher.PUBLIC_SLUG
        dest.mkdir(parents=True)
        old_zip = dest / publisher.PUBLIC_FILENAME
        with zipfile.ZipFile(str(old_zip), "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(publisher.RECIPE + "/calculator.py", "print('old offline')")
        old_sha = hashlib.sha256(old_zip.read_bytes()).hexdigest()
        (dest / "SHA256SUMS.txt").write_text(
            old_sha + "  " + publisher.PUBLIC_FILENAME + "\n"
        )
        (dest / "index.html").write_text(
            "<title>Farm Enterprise Economics</title><a href=\""
            + publisher.PUBLIC_FILENAME + "\">Download</a>"
        )
        (dest / ".htaccess").write_text("Options -Indexes\n")

        with self.assertRaisesRegex(ValueError, "RIGHTS_CLEARANCE_EVIDENCE_MISSING"):
            publisher.publish(
                self.inbox, self.webroot, release_authorized=True,
                uncertified_preview=True, expected_sha256=self.sha,
            )
        self.assertEqual(hashlib.sha256(old_zip.read_bytes()).hexdigest(), old_sha)
        self.assertIn("Download", (dest / "index.html").read_text())


    def test_preview_selects_exact_verified_digest_with_other_receipts_present(self):
        recipe = publisher.RECIPE
        second_zip = self.base / "second.zip"
        with zipfile.ZipFile(str(second_zip), "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(recipe + "/calculator.py", "print('another offline edition')")
        second_sha = hashlib.sha256(second_zip.read_bytes()).hexdigest()
        incoming = self.inbox / "incoming" / recipe
        (incoming / (second_sha + ".zip.partial")).write_bytes(second_zip.read_bytes())
        (incoming / (second_sha + ".json.partial")).write_text(json.dumps({
            "name": "Another private edition",
            "recipe": recipe,
            "artifact_sha256": second_sha,
            "qa_status": "passed",
            "commercial_status": "private_internal_qa_pass_not_published",
            "price": None,
            "public_listing_enabled": False,
            "owner_publication_approval": False,
        }))
        receiver.finalize(self.inbox, recipe, second_sha)

        with self.assertRaisesRegex(ValueError, "RIGHTS_CLEARANCE_EVIDENCE_MISSING"):
            publisher.publish(
                self.inbox, self.webroot, release_authorized=True,
                uncertified_preview=True, expected_sha256=self.sha,
            )
        self.assertFalse((self.webroot / "factory-releases").exists())


if __name__ == "__main__":
    unittest.main()
