import hashlib
import os
import pathlib
import tempfile
import unittest
from f01_offline_escrow_readback_gate_20261030 import Blocked,verify

class TestEscrowReadback(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup)
        self.a=pathlib.Path(self.t.name)/'a.enc'; self.b=pathlib.Path(self.t.name)/'b.enc'
        self.a.write_bytes(b'Encrypted synthetic fixture only.'*5)
        self.b.write_bytes(self.a.read_bytes())
        self.sha=hashlib.sha256(self.a.read_bytes()).hexdigest()
    def test_valid_distinct_copies(self):
        r=verify(self.a,self.b,self.sha)
        self.assertEqual(r['status'],'TWO_LOCAL_COPIES_HASH_MATCH')
        self.assertFalse(r['factory_stop_verified'])
    def test_hash_mismatch(self):
        with self.assertRaisesRegex(Blocked,'HASH_OR_SIZE_MISMATCH'):verify(self.a,self.b,'0'*64)
    def test_changed_readback(self):
        self.b.write_bytes(b'Other synthetic content'*10)
        with self.assertRaisesRegex(Blocked,'HASH_OR_SIZE_MISMATCH'):verify(self.a,self.b,self.sha)
    def test_same_file(self):
        with self.assertRaisesRegex(Blocked,'SAME_FILE'):verify(self.a,self.a,self.sha)
    def test_symlink(self):
        self.b.unlink();self.b.symlink_to(self.a)
        with self.assertRaisesRegex(Blocked,'INPUT_UNAVAILABLE_OR_LINKED'):verify(self.a,self.b,self.sha)
    def test_parent_symlink(self):
        linked=pathlib.Path(self.t.name)/'alias'; linked.symlink_to(self.t.name, target_is_directory=True)
        with self.assertRaisesRegex(Blocked,'INPUT_UNAVAILABLE_OR_LINKED'):
            verify(linked/'a.enc',self.b,self.sha)
    def test_fifo(self):
        self.b.unlink();os.mkfifo(self.b)
        with self.assertRaisesRegex(Blocked,'INPUT_UNAVAILABLE_OR_LINKED|UNSAFE_OR_INVALID_FILE'):verify(self.a,self.b,self.sha)
    def test_empty(self):
        self.b.write_bytes(b'')
        with self.assertRaisesRegex(Blocked,'UNSAFE_OR_INVALID_FILE'):verify(self.a,self.b,self.sha)
    def test_invalid_digest(self):
        with self.assertRaisesRegex(Blocked,'EXPECTED_SHA256_REQUIRED'):verify(self.a,self.b,'bad')

if __name__=='__main__':unittest.main()
