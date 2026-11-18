"""Destructive cleanup helper unit tests (NO execution of cleanup)."""
import ast
import hashlib
import pathlib
import sqlite3
import tempfile
import unittest
import zlib

from scripts import factory_cpanel_nov5_a_exact_cleanup_20261118 as cleanup


class SurgicalSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = pathlib.Path(self.temp.name)
        self.raw = folder / 'test.sqlite3'
        conn=sqlite3.connect(str(self.raw))
        conn.execute('CREATE TABLE t(id INTEGER PRIMARY KEY, data TEXT)')
        conn.execute('INSERT INTO t(data) VALUES(?)', ('integrity',))
        conn.commit()
        conn.close()
        self.plain=self.raw.read_bytes()
        c=zlib.compressobj(level=1,wbits=31)
        compressed=c.compress(self.plain)+c.flush(zlib.Z_FINISH)
        self.gz=folder/'test.sqlite3.gz'
        self.gz.write_bytes(compressed)
        self.gz.chmod(0o600)
        self.old=(cleanup.RAW_SIZE, cleanup.RAW_SHA, cleanup.GZ_SIZE, cleanup.GZ_SHA)
        self.addCleanup(self.restore)
        cleanup.RAW_SIZE=len(self.plain)
        cleanup.RAW_SHA=hashlib.sha256(self.plain).hexdigest()
        cleanup.GZ_SIZE=len(compressed)
        cleanup.GZ_SHA=hashlib.sha256(compressed).hexdigest()

    def restore(self):
        cleanup.RAW_SIZE,cleanup.RAW_SHA,cleanup.GZ_SIZE,cleanup.GZ_SHA=self.old

    def test_wrong_approval_aborts_before_source_access(self):
        with self.assertRaisesRegex(RuntimeError,'EXACT_OWNER_DELEGATION_NOT_PRESENT'):
            cleanup.execute('INCORRECT_APPROVAL')
        self.assertTrue(self.raw.exists())

    def test_valid_read_only_raw_sqlite_integrity(self):
        cleanup.hash_raw(self.raw,self.raw.lstat())
        self.assertEqual(self.raw.read_bytes(),self.plain)

    def test_valid_gzip_restores_original_sha_without_disk_writes(self):
        self.assertTrue(cleanup.verify_gzip(self.gz,self.gz.lstat()))
        self.assertEqual(self.raw.read_bytes(),self.plain)

    def test_corrupt_gzip_is_rejected(self):
        x=bytearray(self.gz.read_bytes())
        x[-6]^=0x1
        self.gz.write_bytes(x)
        with self.assertRaises((RuntimeError,zlib.error)):
            cleanup.verify_gzip(self.gz,self.gz.lstat())
        self.assertTrue(self.raw.exists())

    def test_gzip_wrong_sha_rejected(self):
        cleanup.GZ_SHA='0'*64
        with self.assertRaisesRegex(RuntimeError,'GZIP_RESTORE_INVALID'):
            cleanup.verify_gzip(self.gz,self.gz.lstat())

    def test_raw_wrong_sha_rejected(self):
        cleanup.RAW_SHA='f'*64
        with self.assertRaisesRegex(RuntimeError,'RAW_DIGEST_INVALID'):
            cleanup.hash_raw(self.raw,self.raw.lstat())

    def test_only_one_exact_unlink_is_in_source(self):
        tree=ast.parse(pathlib.Path(cleanup.__file__).read_text())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)
               and isinstance(n.func,ast.Attribute)
               and n.func.attr=='unlink']
        self.assertEqual(len(calls),1)
        self.assertEqual(len(calls[0].args),1)
        self.assertIsInstance(calls[0].args[0],ast.Name)
        self.assertEqual(calls[0].args[0].id,'source')


if __name__=='__main__':
    unittest.main()
