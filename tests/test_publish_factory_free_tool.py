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

    def test_release_blocked_without_chatgpt_review_and_real_qc1000(self):
        with self.assertRaisesRegex(ValueError, "QC1000_REQUIRED_FOR_FACTORY_EXIT"):
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


if __name__ == "__main__":
    unittest.main()
