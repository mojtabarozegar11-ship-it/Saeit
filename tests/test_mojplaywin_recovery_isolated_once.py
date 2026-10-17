"""Synthetic isolation tests: never load an actual production backup."""
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.mojplaywin_restore_files_isolated_runner import recover, safe_parts
from scripts.mojplaywin_recovery_stream_vps import readiness


def fixture(members):
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode="w") as t:
        for name,content in members:
            data=content if isinstance(content,bytes) else content.encode()
            h=tarfile.TarInfo(name)
            h.size=len(data)
            t.addfile(h,io.BytesIO(data))
    buf.seek(0)
    return buf


class RecoveryIsolationTests(unittest.TestCase):
    def test_both_primary_file_roots_recover_to_private_temp(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)/"private"
            base.mkdir(mode=0o700)
            report=recover(fixture([("Saeit-staging/app.txt",b"safe fixture"),
                                    ("mojplaywin.com/index.html",b"simple")]),base)
            self.assertTrue(report["restore_complete"])
            self.assertEqual(report["root_count_restored"],2)
            self.assertEqual(report["regular_files_restored"],2)
            self.assertFalse(report["production_modified"])
            self.assertEqual((base/"Saeit-staging"/"app.txt").read_bytes(),b"safe fixture")

    def test_reject_traversal_and_absolute(self):
        for candidate in ("../../outside","/etc/passwd","mojplaywin.com/../../outside","unknown-site/file"):
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    safe_parts(candidate)

    def test_reject_archive_escape(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)/"private";base.mkdir(mode=0o700)
            buf=fixture([("Saeit-staging/ok",b"one"),
                         ("mojplaywin.com/../../outside",b"unsafe")])
            with self.assertRaises(ValueError):
                recover(buf,base)
            self.assertFalse((Path(td)/"outside").exists())

    def test_metadata_no_archive_no_restore_claim(self):
        with tempfile.TemporaryDirectory() as td:
            report=readiness(Path(td))
            self.assertFalse(report["both_primary_archives_complete"])
            self.assertFalse(report["release_permitted"])
            self.assertFalse(report["isolated_restore_performed"])


if __name__=="__main__":
    unittest.main()
