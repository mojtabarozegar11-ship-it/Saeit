"""Offline adversarial checks for owner-only, no-delete Nov5 gzip staging."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zlib

from scripts import factory_cpanel_nov5_stage_one_gzip_20261118 as stager


class StageSafeTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.src = self.root / 'sample.sqlite3'
        db = sqlite3.connect(str(self.src))
        db.execute('create table rows (id integer primary key, val text)')
        db.executemany('insert into rows(val) values(?)',
                       [(str(i)*24,) for i in range(500)])
        db.commit()
        db.close()
        self.plain = self.src.read_bytes()
        comp = zlib.compressobj(level=1, wbits=31)
        self.gz = comp.compress(self.plain) + comp.flush(zlib.Z_FINISH)
        self.dst = self.root / 'sample.sqlite3.gz'
        names = ('ROOT','SOURCE','SOURCE_BYTES','SOURCE_SHA','GZIP_BYTES',
                 'GZIP_SHA','RESERVE_MIB','admission','quota_mib')
        self.old = {k: getattr(stager, k) for k in names}
        self.addCleanup(self.restore)
        stager.ROOT = self.root
        stager.SOURCE = self.src.name
        stager.SOURCE_BYTES = len(self.plain)
        stager.SOURCE_SHA = hashlib.sha256(self.plain).hexdigest()
        stager.GZIP_BYTES = len(self.gz)
        stager.GZIP_SHA = hashlib.sha256(self.gz).hexdigest()
        stager.RESERVE_MIB = 2
        stager.admission = lambda: (self.src, self.dst, self.src.lstat())
        stager.quota_mib = lambda: 20.0

    def restore(self):
        for k,v in self.old.items():
            setattr(stager,k,v)

    def assert_no_temp(self):
        self.assertEqual(list(self.root.glob('*.owner-stage-*')), [])

    def test_success_restores_identical_bytes_without_deleting_source(self):
        r = stager.stage()
        self.assertEqual(r['new_compressed_backup_files_created'], 1)
        self.assertEqual(r['source_raw_files_deleted'], 0)
        self.assertEqual(self.dst.read_bytes(), self.gz)
        self.assertEqual(self.src.read_bytes(), self.plain)
        self.assert_no_temp()

    def test_quota_failure_creates_nothing(self):
        stager.quota_mib = lambda: 1
        with self.assertRaisesRegex(RuntimeError, 'INSUFFICIENT_ACCOUNT_FREE_WITH_RESERVE'):
            stager.stage()
        self.assertFalse(self.dst.exists())
        self.assert_no_temp()

    def test_quota_drop_cleans_own_temp_not_source(self):
        values = iter([20,1])
        stager.quota_mib = lambda: next(values)
        with self.assertRaisesRegex(RuntimeError, 'QUOTA_RESERVE_LOST'):
            stager.stage()
        self.assertFalse(self.dst.exists())
        self.assertEqual(self.src.read_bytes(), self.plain)
        self.assert_no_temp()

    def test_existing_target_cannot_be_overwritten(self):
        self.dst.write_bytes(b'EXISTING')
        with self.assertRaisesRegex(RuntimeError, 'DESTINATION_RACE'):
            stager.stage()
        self.assertEqual(self.dst.read_bytes(), b'EXISTING')
        self.assertEqual(self.src.read_bytes(), self.plain)
        self.assert_no_temp()

    def test_wrong_source_digest_fails_closed(self):
        stager.SOURCE_SHA = '0'*64
        with self.assertRaisesRegex(RuntimeError, 'SOURCE_OR_COMPRESSED_HASH_CHANGED'):
            stager.stage()
        self.assertFalse(self.dst.exists())
        self.assertEqual(self.src.read_bytes(), self.plain)
        self.assert_no_temp()

    def test_wrong_gzip_digest_fails_closed(self):
        stager.GZIP_SHA = 'f'*64
        with self.assertRaisesRegex(RuntimeError, 'SOURCE_OR_COMPRESSED_HASH_CHANGED'):
            stager.stage()
        self.assertFalse(self.dst.exists())
        self.assertEqual(self.src.read_bytes(), self.plain)
        self.assert_no_temp()


if __name__ == '__main__':
    unittest.main()
