"""Offline fail-closed checks for the one-time research-book cPanel publisher."""

import importlib.util
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SCRIPT = next((p for p in (
    HERE / "mpw_c4_atomic_publish.py",
    HERE.parent / "scripts/mpw_research_library_publish_20261108.py",
) if p.is_file()), None)
if SCRIPT is None:
    raise RuntimeError("Standalone publication helper not found")
spec = importlib.util.spec_from_file_location("c4publisher", SCRIPT)
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mpw-c4-test-")
        self.home = Path(self.temp.name) / "zomorod2"
        self.home.mkdir()
        site = self.home / "mojplaywin.com"
        site.mkdir()
        (site / "mpw-editorial").mkdir()
        (site / ".htaccess").write_text("RewriteEngine On\n")
        (site / "passenger_wsgi.py").write_text("application=None\n")
        self.package = self.home / "source.zip"
        members = {
            name: (b"%PDF-1.4\nfixture\n" if name.endswith(".pdf") else b"<!doctype html><title>Fixture</title>")
            for name in publisher.EXACT_FILES - {"release.json"}
        }
        manifest = {
            "release_id": publisher.RELEASE,
            "public_root": "/mpw-editorial/research-library/20261108-c4/",
            "files": {name: {"bytes": len(data), "sha256": publisher.digest(data)} for name, data in members.items()},
        }
        members["release.json"] = json.dumps(manifest).encode("utf-8")
        with zipfile.ZipFile(self.package, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in members.items():
                z.writestr(name, data)
        self.patches = [
            patch.object(publisher, "HOME", self.home),
            patch.object(publisher, "SITE", site),
            patch.object(publisher, "EDITORIAL", site / "mpw-editorial"),
            patch.object(publisher, "PARENT", site / "mpw-editorial/research-library"),
            patch.object(publisher, "TARGET", site / "mpw-editorial/research-library/20261108-c4"),
            patch.object(publisher, "PRIVATE", self.home / ".mpw-research-release-c4"),
            patch.object(publisher, "authorized_user", return_value=True),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_clean_preflight_install_readback_and_recoverable_rollback(self):
        publisher.preflight()
        v = publisher.verify_zip(self.package)
        self.assertEqual(len(v["files"]), 27)
        publisher.install(self.package, "202611080001")
        self.assertTrue((publisher.TARGET / "index.html").is_file())
        publisher.verify_directory(publisher.TARGET, v)
        publisher.rollback("202611080001")
        self.assertFalse(publisher.TARGET.exists())
        self.assertTrue((publisher.PRIVATE / "quarantined-202611080001" / "index.html").is_file())

    def test_existing_release_cannot_be_overwritten(self):
        publisher.PARENT.mkdir()
        publisher.TARGET.mkdir()
        with self.assertRaisesRegex(RuntimeError, "VERSION_ALREADY_PRESENT"):
            publisher.install(self.package, "202611080002")

    def test_tampered_zip_refused(self):
        tampered = self.home / "bad.zip"
        with zipfile.ZipFile(self.package) as z:
            members = {n: z.read(n) for n in z.namelist()}
        members["index.html"] += b"unsafe change"
        with zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in members.items():
                z.writestr(name, data)
        with self.assertRaisesRegex(RuntimeError, "HASH_OR_SIZE_MISMATCH"):
            publisher.verify_zip(tampered)

    def test_unknown_archive_file_refused(self):
        extra = self.home / "extra.zip"
        with zipfile.ZipFile(self.package) as z:
            members = {n: z.read(n) for n in z.namelist()}
        members["unknown.txt"] = b"unsafe"
        with zipfile.ZipFile(extra, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in members.items():
                z.writestr(name, data)
        with self.assertRaisesRegex(RuntimeError, "WRONG_OR_DUPLICATE_ARCHIVE_FILES"):
            publisher.verify_zip(extra)

    def test_symlinked_publication_parent_refused(self):
        elsewhere = self.home / "elsewhere"
        elsewhere.mkdir()
        publisher.PARENT.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "RELEASE_PARENT_COLLISION"):
            publisher.preflight()

    def test_changed_released_file_blocks_rollback(self):
        publisher.install(self.package, "202611080003")
        with open(publisher.TARGET / "index.html", "a") as f:
            f.write("modified after install")
        with self.assertRaisesRegex(RuntimeError, "DEPLOYED_HASH_CHANGED"):
            publisher.rollback("202611080003")
        self.assertTrue(publisher.TARGET.exists())

    def test_invalid_run_id_refused(self):
        with self.assertRaisesRegex(RuntimeError, "INVALID_RUN_ID"):
            publisher.install(self.package, "../../other")

    def test_foreign_package_location_refused(self):
        foreign = Path(self.temp.name) / "outside.zip"
        shutil.copyfile(self.package, foreign)
        with self.assertRaisesRegex(RuntimeError, "ZIP_MUST_BE_OWNED_INSIDE_CPANEL_HOME"):
            publisher.verify_zip(foreign)

    def test_receipt_reuse_refused(self):
        publisher.install(self.package, "202611080004")
        publisher.rollback("202611080004")
        with self.assertRaisesRegex(RuntimeError, "RUN_ALREADY_USED"):
            publisher.install(self.package, "202611080004")

    def test_symlink_inside_release_blocks_rollback(self):
        publisher.install(self.package, "202611080005")
        member = publisher.TARGET / "index.html"
        member.unlink()
        member.symlink_to(self.package)
        with self.assertRaisesRegex(RuntimeError, "RELEASE_FILE_COLLISION"):
            publisher.rollback("202611080005")
        self.assertTrue(publisher.TARGET.exists())


if __name__ == "__main__":
    unittest.main()
