"""Ensure independent personal store bridge accepts only private validated packages."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1] / "scripts"


def load(filename):
    spec = importlib.util.spec_from_file_location(filename, str(ROOT / (filename + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


receiver = load("store_receiver")
adapter = load("personal_factory_adapter")


class PersonalFactoryAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.app = self.home / "mojtaba_personal" / "mojtaba_roozegar_personal_v17"
        self.app.mkdir(parents=True)
        (self.app / "manage.py").write_text("# stub")
        (self.app / "passenger_wsgi.py").write_text("# stub")
        self.public = self.home / "mojplaywin.com" / "mojtaba.roozegar"
        self.public.mkdir(parents=True)
        (self.public / ".htaccess").write_text(
            "PassengerBaseURI /mojtaba.roozegar\nPassengerAppRoot " + str(self.app) + "\n"
        )
        self.inbox = self.home / ".saeit-factory-inbox"
        self.destination = self.app / "var" / "factory_imports"
        self.recipe = "farm_enterprise_economics"
        sample = self.home / "sample.zip"
        with zipfile.ZipFile(str(sample), "w") as zipf:
            zipf.writestr(self.recipe + "/calculator.py", "print(1)")
        self.sha = hashlib.sha256(sample.read_bytes()).hexdigest()
        path = self.inbox / "incoming" / self.recipe
        path.mkdir(parents=True)
        (path / (self.sha + ".zip.partial")).write_bytes(sample.read_bytes())
        (path / (self.sha + ".json.partial")).write_text(json.dumps({
            "recipe": self.recipe, "name": "Farm Enterprise Economics Toolkit",
            "artifact_sha256": self.sha, "qa_status": "passed",
            "commercial_status": "private_internal_qa_pass_not_published",
            "public_listing_enabled": False, "owner_publication_approval": False, "price": None
        }))
        receiver.finalize(self.inbox, self.recipe, self.sha)

    def test_private_transfer_and_idempotent_repeat(self):
        first = adapter.stage(self.inbox, self.app, self.public, self.destination)
        self.assertEqual(first, {"examined": 1, "updated": 1, "unchanged": 0})
        artifact = self.destination / "packages" / self.recipe / (self.sha + ".zip")
        self.assertTrue(artifact.is_file())
        self.assertEqual(artifact.stat().st_mode & 0o777, 0o600)
        record = json.loads((self.destination / "private_catalog.json").read_text())
        self.assertFalse(record["items"][0]["publication_authorized"])
        self.assertFalse(record["items"][0]["storefront_listing_created"])
        self.assertEqual(record["public_products"], 0)
        second = adapter.stage(self.inbox, self.app, self.public, self.destination)
        self.assertEqual(second["updated"], 0)
        self.assertEqual(second["unchanged"], 1)

    def test_corrupted_shared_package_is_rejected(self):
        package = self.inbox / "packages" / self.recipe / (self.sha + ".zip")
        package.write_bytes(b"invalid")
        with self.assertRaises(RuntimeError):
            adapter.stage(self.inbox, self.app, self.public, self.destination)

    def test_rejects_path_outside_personal_application(self):
        with self.assertRaises(RuntimeError):
            adapter.stage(self.inbox, self.app, self.public, self.home / "public_assets")

    def test_rejects_mismatched_passenger_application_root(self):
        (self.public / ".htaccess").write_text("PassengerAppRoot /not/the/personal/app\n")
        with self.assertRaises(RuntimeError):
            adapter.stage(self.inbox, self.app, self.public, self.destination)

    def test_no_receipts_leaves_no_catalog(self):
        empty = self.home / "empty"
        empty.mkdir()
        result = adapter.stage(empty, self.app, self.public, self.destination)
        self.assertEqual(result["examined"], 0)


if __name__ == "__main__":
    unittest.main()
