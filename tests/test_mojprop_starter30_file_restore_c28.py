"""Offline tests for file backup/isolated restoration only; never touch cPanel."""
from pathlib import Path
import getpass
import json
import tempfile
import unittest
from unittest.mock import patch

from scripts import mojprop_starter30_file_restore_c28 as mod


class C28ScopedRealRestore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / 'mojplaywin.com'
        self.vault = self.home / '.mojprop-static-restore-evidence'
        (self.root / 'moj-prop' / 'catalog').mkdir(parents=True)
        (self.root / 'moj-prop' / 'index.html').write_bytes(b'A'*150)
        (self.root / 'moj-prop' / 'catalog' / 'index.html').write_bytes(b'B'*170)
        self.params = dict(home=self.home, root=self.root, vault=self.vault,
                           owner=getpass.getuser(), run_id='172900101')

    def test_backup_and_independent_private_restore_with_no_live_write(self):
        originals = [ (self.root/p).read_bytes() for p in mod.PUBLIC_FILES ]
        result = mod.audit_and_restore(**self.params)
        self.assertTrue(result['verified_isolated_restore'])
        self.assertFalse(result['release_permitted'])
        self.assertFalse(result['subsite_isolation_proven'])
        self.assertFalse(result['all_site_backup_proven'])
        self.assertEqual(originals, [(self.root/p).read_bytes() for p in mod.PUBLIC_FILES])
        stored=json.loads((self.vault / '172900101' / 'manifest.json').read_text())
        self.assertEqual(len(stored['sha256']), 2)
        for directory in ('backup','isolated-restore'):
            self.assertEqual(len(list((self.vault/'172900101'/directory).iterdir())),2)
        self.assertEqual((self.vault/'172900101').stat().st_mode & 0o077, 0)

    def test_existing_run_id_cannot_overwrite_backup(self):
        mod.audit_and_restore(**self.params)
        with self.assertRaises(FileExistsError):
            mod.audit_and_restore(**self.params)

    def test_refuse_missing_catalog_without_persisting_backup(self):
        (self.root/'moj-prop/catalog/index.html').unlink()
        with self.assertRaises(OSError):
            mod.audit_and_restore(**self.params)
        self.assertFalse(self.vault.exists())

    def test_refuse_public_symlink_even_if_target_belongs_to_user(self):
        q=self.root/'moj-prop/catalog/index.html'
        q.unlink()
        q.symlink_to(self.root/'moj-prop/index.html')
        with self.assertRaises(RuntimeError):
            mod.audit_and_restore(**self.params)

    def test_refuse_unsafe_world_writable_public_root(self):
        self.root.chmod(0o777)
        with self.assertRaises(RuntimeError):
            mod.audit_and_restore(**self.params)

    def test_refuse_out_of_scope_destination(self):
        self.params['vault'] = self.home/'evil'
        with self.assertRaises(ValueError):
            mod.audit_and_restore(**self.params)

    def test_refuse_identity_mismatch(self):
        self.params['owner']='definitely-not-this-user'
        with self.assertRaises(RuntimeError):
            mod.audit_and_restore(**self.params)

    def test_refuse_bad_run_identifiers(self):
        for bad in ('0', '01', '../tmp', '2;rm', '', '1'*22):
            self.params['run_id']=bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                mod.audit_and_restore(**self.params)

    def test_refuse_unsafe_world_writable_archive(self):
        self.vault.mkdir(mode=0o777)
        self.vault.chmod(0o777)
        with self.assertRaises(RuntimeError):
            mod.audit_and_restore(**self.params)

    def test_refuse_empty_tiny_or_oversized_public_html(self):
        path=self.root/'moj-prop/index.html'
        for body in (b'', b'too small', b'X'*(mod.MAX_BYTES+1)):
            path.write_bytes(body)
            with self.subTest(length=len(body)), self.assertRaises(RuntimeError):
                mod.audit_and_restore(**self.params)

    def test_refuse_shared_hardlinks_to_untrusted_public_input(self):
        source=self.root/'moj-prop/index.html'
        (self.home/'side-link').hardlink_to(source)
        with self.assertRaises(RuntimeError):
            mod.audit_and_restore(**self.params)

    def test_cannot_claim_revenue_payment_database_or_full_restore(self):
        report = mod.audit_and_restore(**self.params)
        for key in ('database_backup_or_restore','all_site_backup_proven',
                    'subsite_isolation_proven','release_permitted',
                    'payment_permitted','revenue_proven'):
            self.assertIs(report[key], False)


if __name__ == '__main__':
    unittest.main()
