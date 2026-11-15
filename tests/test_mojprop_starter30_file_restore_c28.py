"""C28 offline capability, quota and replay checks. Never connects to cPanel."""
from pathlib import Path
import getpass
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from scripts import mojprop_starter30_file_restore_c28 as mod


def enough_quota(_fd, _owner, _bytes):
    return True


class C28ScopedRealRestore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / "mojplaywin.com"
        self.vault = self.home / ".mojprop-static-restore-evidence"
        (self.root / "moj-prop" / "catalog").mkdir(parents=True)
        (self.root / "moj-prop" / "index.html").write_bytes(b"A" * 150)
        (self.root / "moj-prop" / "catalog" / "index.html").write_bytes(b"B" * 170)
        self.params = dict(home=self.home, root=self.root, vault=self.vault,
                           owner=getpass.getuser(), run_id="172900101",
                           approval_id="9873211", quota_probe=enough_quota)

    def test_two_public_file_backup_and_private_isolated_restore(self):
        originals = [(self.root / Path(*x)).read_bytes() for x in mod.PUBLIC_FILES]
        result = mod.audit_and_restore(**self.params)
        self.assertTrue(result["isolated_two_file_restore"])
        self.assertFalse(result["subsite_isolation_proven"])
        self.assertFalse(result["all_site_backup_proven"])
        self.assertFalse(result["release_permitted"])
        self.assertEqual(originals, [(self.root / Path(*x)).read_bytes() for x in mod.PUBLIC_FILES])
        manifest = json.loads((self.vault / "172900101" / "manifest.json").read_text())
        self.assertEqual(len(manifest["sha256"]), 2)
        self.assertEqual(manifest["approval_id"], "9873211")
        for directory in ("backup", "isolated-restore"):
            self.assertEqual(len(list((self.vault / "172900101" / directory).iterdir())), 2)
        self.assertEqual((self.vault / "172900101").stat().st_mode & 0o077, 0)

    def test_single_use_approval_persists_outside_renameable_vault(self):
        mod.audit_and_restore(**self.params)
        claim = self.home / ".mojprop-c28-approval-9873211.used"
        self.assertEqual(claim.read_bytes(), b"CONSUMED\n")
        self.assertFalse((self.vault / "approval-9873211.used").exists())

    def test_real_quota_parser_needs_account_block_and_inode_headroom(self):
        fd = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY)
        try:
            class Out:
                stdout = ("Disk quotas for user sample (uid 1001):\n"
                          "Filesystem space quota limit grace files quota limit grace\n"
                          "/dev/vda1 12K 1024M 2048M 20 2000 4000\n")
            with patch.object(mod.subprocess, "run", return_value=Out()):
                self.assertTrue(mod._quota_evidence(fd, getpass.getuser(), 8192))
        finally:
            os.close(fd)

    def test_real_quota_soft_limit_nearly_exhausted_is_denied(self):
        fd = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY)
        try:
            class Out:
                stdout = "/dev/vda1 1023M 1024M 2048M 20 2000 4000\n"
            with patch.object(mod.subprocess, "run", return_value=Out()):
                self.assertFalse(mod._quota_evidence(fd, getpass.getuser(), 8192))
        finally:
            os.close(fd)

    def test_real_quota_inode_limit_nearly_exhausted_is_denied(self):
        fd = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY)
        try:
            class Out:
                stdout = "/dev/vda1 12K 1024M 2048M 1999 2000 4000\n"
            with patch.object(mod.subprocess, "run", return_value=Out()):
                self.assertFalse(mod._quota_evidence(fd, getpass.getuser(), 8192))
        finally:
            os.close(fd)

    def test_exact_run_replay_denied(self):
        mod.audit_and_restore(**self.params)
        with self.assertRaises(FileExistsError):
            mod.audit_and_restore(**self.params)

    def test_same_authorization_replay_with_new_run_denied(self):
        mod.audit_and_restore(**self.params)
        self.params["run_id"] = "172900102"
        with self.assertRaises(FileExistsError):
            mod.audit_and_restore(**self.params)
        self.assertFalse((self.vault / "172900102").exists())

    def test_distinct_approved_nonce_can_recover_to_new_private_run(self):
        mod.audit_and_restore(**self.params)
        self.params["run_id"] = "172900102"
        self.params["approval_id"] = "9873212"
        result = mod.audit_and_restore(**self.params)
        self.assertTrue(result["isolated_two_file_restore"])

    def test_missing_catalog_refused_without_create(self):
        (self.root / "moj-prop/catalog/index.html").unlink()
        with self.assertRaises(OSError):
            mod.audit_and_restore(**self.params)
        self.assertFalse(self.vault.exists())

    def test_refuse_public_symlink_and_hardlink(self):
        src = self.root / "moj-prop/catalog/index.html"
        src.unlink()
        src.symlink_to(self.root / "moj-prop/index.html")
        with self.assertRaises(OSError):
            mod.audit_and_restore(**self.params)
        src.unlink()
        os.link(self.root / "moj-prop/index.html", src)
        with self.assertRaises(RuntimeError):
            mod.audit_and_restore(**self.params)

    def test_refuse_symlinked_catalog_ancestor(self):
        d = self.root / "moj-prop/catalog"
        (d / "index.html").unlink()
        d.rmdir()
        d.symlink_to(self.home)
        with self.assertRaises(OSError):
            mod.audit_and_restore(**self.params)

    def test_refuse_unsafe_world_writable_root(self):
        self.root.chmod(0o777)
        with self.assertRaises(RuntimeError):
            mod.audit_and_restore(**self.params)

    def test_refuse_out_of_scope_destination(self):
        self.params["vault"] = self.home / "unsafe"
        with self.assertRaises(ValueError):
            mod.audit_and_restore(**self.params)

    def test_refuse_identity_mismatch(self):
        self.params["owner"] = "definitely-not-this-user"
        with self.assertRaises(RuntimeError):
            mod.audit_and_restore(**self.params)

    def test_bad_run_and_approval_ids(self):
        for key in ("run_id", "approval_id"):
            for bad in ("0", "01", "../tmp", "2;rm", "", "1" * 22):
                self.params[key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    mod.audit_and_restore(**self.params)
                self.params[key] = "172900101" if key == "run_id" else "9873211"

    def test_existing_world_writable_private_vault_denied(self):
        self.vault.mkdir(mode=0o700)
        self.vault.chmod(0o777)
        with self.assertRaises(RuntimeError):
            mod.audit_and_restore(**self.params)

    def test_too_small_and_oversized_sources_denied(self):
        p = self.root / "moj-prop/index.html"
        for body in (b"", b"bad", b"X" * (mod.MAX_BYTES + 1)):
            p.write_bytes(body)
            with self.subTest(size=len(body)), self.assertRaises(RuntimeError):
                mod.audit_and_restore(**self.params)

    def test_account_quota_evidence_missing_fails_without_writes(self):
        self.params["quota_probe"] = lambda *args: False
        with self.assertRaises(RuntimeError):
            mod.audit_and_restore(**self.params)
        self.assertFalse(self.vault.exists())

    def test_account_quota_probe_must_return_actual_boolean_true(self):
        self.params["quota_probe"] = lambda *args: 1
        with self.assertRaises(RuntimeError):
            mod.audit_and_restore(**self.params)

    def test_quantity_units(self):
        self.assertEqual(mod._quantity("1K"), 1024)
        self.assertEqual(mod._quantity("1M"), 1024 ** 2)
        self.assertEqual(mod._quantity("2G"), 2 * 1024 ** 3)
        with self.assertRaises(RuntimeError):
            mod._quantity("unlimited")

    def test_quota_missing_command_refused(self):
        fd = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY)
        try:
            with patch.object(mod.subprocess, "run", side_effect=FileNotFoundError):
                self.assertFalse(mod._quota_evidence(fd, getpass.getuser(), 2048))
        finally:
            os.close(fd)

    def test_vault_ancestor_renamed_and_symlinked_does_not_redirect_to_live_site(self):
        original = mod._mkdir
        vault = self.vault
        root = self.root
        swapped = {"yes": False}

        def swap_after_open(parent, name, uid, *, unique=False):
            descriptor = original(parent, name, uid, unique=unique)
            if name == ".mojprop-static-restore-evidence" and not swapped["yes"]:
                vault.rename(self.home / "displaced-private-vault")
                vault.symlink_to(root, target_is_directory=True)
                swapped["yes"] = True
            return descriptor

        with patch.object(mod, "_mkdir", side_effect=swap_after_open):
            result = mod.audit_and_restore(**self.params)
        self.assertTrue(result["isolated_two_file_restore"])
        self.assertFalse((root / "172900101").exists())
        self.assertFalse((root / "approval-9873211.used").exists())
        self.assertTrue((self.home / "displaced-private-vault" / "172900101" / "manifest.json").is_file())

    def test_live_source_replaced_after_initial_read_does_not_pass(self):
        original = mod._mkdir
        replaced = {"yes": False}
        path = self.root / "moj-prop/index.html"

        def swap_during_run(parent, name, uid, *, unique=False):
            descriptor = original(parent, name, uid, unique=unique)
            if name == "backup" and not replaced["yes"]:
                replaced["yes"] = True
                path.write_bytes(b"changed" * 25)
            return descriptor
        with patch.object(mod, "_mkdir", side_effect=swap_during_run):
            with self.assertRaises(RuntimeError):
                mod.audit_and_restore(**self.params)

    def test_quota_exception_cleans_only_this_private_run_and_consumes_nonce(self):
        originals = [(self.root / Path(*x)).read_bytes() for x in mod.PUBLIC_FILES]
        real_write = mod._write
        triggered = {"count": 0}

        def fail_one_copy(fd, name, content):
            if name == "file-1.bin":
                triggered["count"] += 1
                if triggered["count"] == 2:
                    raise OSError(122, "Disk quota exceeded")
            return real_write(fd, name, content)

        with patch.object(mod, "_write", side_effect=fail_one_copy):
            with self.assertRaises(OSError):
                mod.audit_and_restore(**self.params)
        self.assertFalse((self.vault / "172900101").exists())
        self.assertTrue((self.home / ".mojprop-c28-approval-9873211.used").exists())
        self.assertEqual(originals, [(self.root / Path(*x)).read_bytes() for x in mod.PUBLIC_FILES])
        self.params["run_id"] = "172900102"
        with self.assertRaises(FileExistsError):
            mod.audit_and_restore(**self.params)

    def test_manifest_or_private_write_failure_does_not_touch_live_tree(self):
        original = mod._write
        def fail_manifest(fd, name, content):
            if name == "manifest.json":
                raise OSError(28, "No space left on device")
            return original(fd, name, content)
        with patch.object(mod, "_write", side_effect=fail_manifest):
            with self.assertRaises(OSError):
                mod.audit_and_restore(**self.params)
        self.assertFalse((self.vault / "172900101").exists())
        self.assertEqual((self.root / "moj-prop/index.html").read_bytes(), b"A" * 150)
        self.assertEqual((self.root / "moj-prop/catalog/index.html").read_bytes(), b"B" * 170)

    def test_never_grants_payment_or_full_site_recovery(self):
        report = mod.audit_and_restore(**self.params)
        for key in ("database_backup_or_restore", "all_site_backup_proven",
                    "subsite_isolation_proven", "release_permitted",
                    "payment_permitted", "revenue_proven", "live_files_modified"):
            self.assertIs(report[key], False)


if __name__ == "__main__":
    unittest.main()
