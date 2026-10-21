"""Complete synthetic backup -> GPG -> independent isolated restore integration.

Never loads production records, SSH credentials, public web roots or a live
database. The restore target is a TemporaryDirectory, destroyed after test.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zlib
from pathlib import Path

from scripts import mojplaywin_backup_encrypt_vps_gpg as encrypt
from scripts import mojplaywin_backup_gzip_source_v3 as source
from scripts import mojplaywin_backup_gzip_recovery_v3 as recovery

STEM = "mojplaywin_20261020"


def source_to_gpg_and_recover(root, kind, command, expected):
    compressed = io.BytesIO()
    metrics = source.compress_process(command, out=compressed)
    assert metrics["raw_bytes"] == len(expected)
    receipt = encrypt.store(io.BytesIO(compressed.getvalue()), kind, root=root,
                            keyroot=root, minimum_free=0, stem=STEM,
                            source_encoding="gzip-with-footer-v1")
    assert receipt["decryption_verified"] and not receipt["release_permitted"]
    recovered = io.BytesIO()
    assert recovery.decode_archive(kind, home=root, stem=STEM, out=recovered) == len(expected)
    assert recovered.getvalue() == expected
    return recovered.getvalue()


@unittest.skipUnless(shutil.which("gpg"), "GPG required for fixture integration")
class PrivatePipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory(prefix="v3-synthetic-isolated-")
        self.addCleanup(td.cleanup)
        self.base = Path(td.name)

    def test_both_archives_and_isolated_sql_tar_recovery(self):
        sql = (b"CREATE TABLE fixture_counter(id INT);\n"
               b"INSERT INTO fixture_counter VALUES(7);\n" * 30)
        sql_script = "import sys;sys.stdout.buffer.write(" + repr(sql) + ")"
        recovered_sql = source_to_gpg_and_recover(
            self.base, "mysql", [sys.executable, "-c", sql_script], sql)
        self.assertIn(b"CREATE TABLE fixture_counter", recovered_sql)

        file_root = self.base / "source_fixture"
        file_root.mkdir()
        (file_root / "README.txt").write_text("Recovery test only. No real user data.\n")
        (file_root / "demo.txt").write_bytes(b"simulated site binary content" * 200)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w") as tar:
            for name in ("README.txt", "demo.txt"):
                tar.add(file_root / name, arcname="main-site/" + name)
        expected_tar = archive.getvalue()
        tar_script = ("import sys;sys.stdout.buffer.write(" + repr(expected_tar) + ")")
        recovered_tar = source_to_gpg_and_recover(
            self.base, "files", [sys.executable, "-c", tar_script], expected_tar)
        self.assertTrue(recovery.both_ready(home=self.base, stem=STEM))
        with tarfile.open(fileobj=io.BytesIO(recovered_tar), mode="r:") as tar:
            names = tar.getnames()
            self.assertEqual(names, ["main-site/README.txt", "main-site/demo.txt"])
            # Read individual known fixture members only; no extractall or
            # risk of tar directory traversal into host files.
            self.assertEqual(
                tar.extractfile("main-site/README.txt").read(),
                b"Recovery test only. No real user data.\n")

        for kind in ("mysql", "files"):
            manifest = self.base / ".private-mojplaywin-offhost-backups" / (
                STEM + "_" + kind + "_gpgv2.manifest.json")
            meta = json.loads(manifest.read_text())
            self.assertFalse(meta["isolated_restoration_completed"])
            self.assertFalse(meta["release_permitted"])
            self.assertEqual(meta["source_encoding"], "gzip-with-footer-v1")
            self.assertTrue(meta["source_completion_footer_verified"])

    def test_partial_dump_creates_no_complete_archive_or_manifest(self):
        failed = [sys.executable, "-c",
                  "import sys;sys.stdout.buffer.write(b'partial'*300);sys.exit(5)"]
        output = io.BytesIO()
        with self.assertRaises(RuntimeError):
            source.compress_process(failed, out=output)
        self.assertFalse(output.getvalue().endswith(source.MARKER))
        with self.assertRaises(Exception):
            encrypt.store(io.BytesIO(output.getvalue()), "mysql",
                          root=self.base, keyroot=self.base, minimum_free=0,
                          stem=STEM, source_encoding="gzip-with-footer-v1")
        folder = self.base / ".private-mojplaywin-offhost-backups"
        self.assertFalse((folder / (STEM + "_mysql_gpgv2.gpg")).exists())
        self.assertFalse((folder / (STEM + "_mysql_gpgv2.manifest.json")).exists())
        self.assertFalse(recovery.both_ready(home=self.base, stem=STEM))


if __name__ == "__main__":
    unittest.main()
