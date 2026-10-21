"""Synthetic-only private encrypted backup extraction tests."""
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from tools.moj_commerce_v12_restore_extra_webroots_isolated import restore


def source(items, *,symlink=False):
    b=io.BytesIO()
    with tarfile.open(fileobj=b,mode='w') as tar:
        for name in items:
            data=b'test file'
            t=tarfile.TarInfo(name)
            t.size=len(data)
            tar.addfile(t,io.BytesIO(data))
        if symlink:
            t=tarfile.TarInfo('root-one/link')
            t.type=tarfile.SYMTYPE
            t.linkname='/etc/private'
            tar.addfile(t)
    b.seek(0)
    return b

class IsolatedRestoreTests(unittest.TestCase):
    def test_complete_synthetic_restore_isolated(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'private'
            p.mkdir(mode=0o700)
            r=restore(source(['root-one/a','root-two/b','root-three/c']),p)
            self.assertTrue(r['extra_root_restore_complete'])
            self.assertEqual(r['root_count_restored'],3)
            self.assertEqual(r['regular_files_restored'],3)
            self.assertEqual((p/'root-two/b').read_bytes(),b'test file')
            self.assertFalse(r['entire_cpanel_tenant_restore_proven'])
            self.assertFalse(r['release_permitted'])

    def test_reject_out_of_scope_paths_and_symlinks(self):
        for name in ['/etc/file','../secrets','mojplaywin.com/file','Saeit-staging/file']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                p=Path(td)/'private'
                p.mkdir(mode=0o700)
                with self.assertRaises(ValueError):
                    restore(source(['root-one/a','root-two/b',name]),p)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'private'
            p.mkdir(mode=0o700)
            with self.assertRaises(ValueError):
                restore(source(['root-one/a','root-two/b','root-three/c'],symlink=True),p)

    def test_reject_public_destination(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'unsafe'
            p.mkdir(mode=0o755)
            with self.assertRaises(ValueError):
                restore(source(['root-one/a','root-two/b','root-three/c']),p)

if __name__=='__main__':unittest.main()
