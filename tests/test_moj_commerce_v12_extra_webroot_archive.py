"""Synthetic-only validation of separate extra-root recovery stream."""
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from tools.moj_commerce_v12_extra_webroot_archive_verify import inspect
from scripts.mojplaywin_recovery_stream_vps import discover_extra


def tar_fixture(paths):
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w') as tf:
        for name in paths:
            data=b'dummy-safe-backup-data'
            info=tarfile.TarInfo(name)
            info.size=len(data)
            tf.addfile(info,io.BytesIO(data))
    out.seek(0)
    return out

class ExtraRootVerificationTests(unittest.TestCase):
    def test_extra_roots_parse_without_extraction_or_approval(self):
        report=inspect(tar_fixture(['extra-site-1/index.html','extra-site-2/index.html',
                                    'extra-site-3/index.html']))
        self.assertEqual(report['archive_roots_aggregate_count'],3)
        self.assertEqual(report['totals']['regular'],3)
        self.assertFalse(report['safe_isolated_extraction_performed'])
        self.assertFalse(report['release_permitted'])

    def test_protected_main_roots_and_escape_cannot_be_misclassified(self):
        for name in ['Saeit-staging/index.html','../etc/file.txt',
                     '/var/private/secret','mojplaywin.com/assets/logo.png']:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    inspect(tar_fixture([name]))

    def test_extra_archive_no_manifest_is_not_ready(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            (home/'.private-mojplaywin-offhost-backups').mkdir()
            with self.assertRaises(RuntimeError):
                discover_extra(home)

if __name__=='__main__':unittest.main()
