"""Synthetic isolation tests: never load an actual production backup."""
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.mojplaywin_restore_files_isolated_runner import recover, safe_parts, safe_failure_code
from scripts.mojplaywin_recovery_stream_vps import readiness, discover, STEM_RE, NEW_MANIFEST_RE


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

    def test_source_account_absolute_symlink_is_rebased_inside_sandbox(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)/"private"
            base.mkdir(mode=0o700)
            buf=io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                for name in ("Saeit-staging/assets/data.txt", "mojplaywin.com/index.html"):
                    raw=b"safe synthetic content"
                    item=tarfile.TarInfo(name)
                    item.size=len(raw)
                    tar.addfile(item,io.BytesIO(raw))
                link=tarfile.TarInfo("mojplaywin.com/alias.txt")
                link.type=tarfile.SYMTYPE
                link.linkname="/home/zomorod2/Saeit-staging/assets/data.txt"
                tar.addfile(link)
            buf.seek(0)
            report=recover(buf,base)
            restored=base/"mojplaywin.com"/"alias.txt"
            self.assertTrue(report["restore_complete"])
            self.assertTrue(restored.is_symlink())
            self.assertEqual(restored.resolve(),base/"Saeit-staging"/"assets"/"data.txt")
            self.assertFalse(restored.readlink().is_absolute())

    def test_absolute_symlink_outside_two_backed_roots_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)/"private"
            base.mkdir(mode=0o700)
            buf=io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                for name in ("Saeit-staging/a", "mojplaywin.com/b"):
                    raw=b"data"
                    item=tarfile.TarInfo(name)
                    item.size=len(raw)
                    tar.addfile(item,io.BytesIO(raw))
                link=tarfile.TarInfo("mojplaywin.com/outside")
                link.type=tarfile.SYMTYPE
                link.linkname="/etc/passwd"
                tar.addfile(link)
            buf.seek(0)
            with self.assertRaisesRegex(ValueError, "unbacked absolute archive link"):
                recover(buf,base)
            self.assertFalse((base/"mojplaywin.com"/"outside").exists())

    def test_failure_diagnostics_are_fixed_codes_without_private_paths(self):
        self.assertEqual(safe_failure_code(ValueError(
            "absolute archive link cannot be restored into sandbox")), "absolute_link")
        self.assertEqual(safe_failure_code(ValueError(
            "insufficient isolated capacity")), "capacity")
        self.assertEqual(safe_failure_code(OSError(
            "/home/private/customer-data/secret.txt")), "isolated_io")
        self.assertEqual(safe_failure_code(ValueError(
            "/home/private/customer-data/secret.txt")), "invalid_tar_member")

    def test_discovery_fails_closed_without_exact_verified_pair(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/".private-mojplaywin-offhost-backups"
            root.mkdir(mode=0o700)
            names=[
                "mojplaywin_20261021T153000Z_1111111111111111_mysql_gpgv2.manifest.json",
                "mojplaywin_20261021T153100Z_2222222222222222_mysql_gpgv2.manifest.json",
            ]
            for name in names:
                (root/name).write_text("{}", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                discover(Path(td))
        self.assertIsNone(STEM_RE.fullmatch("../other-site"))
        self.assertIsNotNone(NEW_MANIFEST_RE.fullmatch(names[0]))

    def test_metadata_no_archive_no_restore_claim(self):
        with tempfile.TemporaryDirectory() as td:
            report=readiness(Path(td))
            self.assertFalse(report["both_primary_archives_complete"])
            self.assertFalse(report["release_permitted"])
            self.assertFalse(report["isolated_restore_performed"])


if __name__=="__main__":
    unittest.main()
