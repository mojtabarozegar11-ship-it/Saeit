"""Test disabled-only isolated MojPlayWin payment update and rollback guards."""
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SRC=Path(__file__).resolve().parents[1]/"scripts"/"mojplaywin_crypto_safe_upgrade.py"
spec=importlib.util.spec_from_file_location("mojplaywin_crypto_safe_upgrade",SRC)
updater=importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class TestStandAloneUpgrade(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.target=self.root/"website"/"checkout"/"crypto"
        self.state=self.root/"private"
        self.stage=self.root/"staging"
        for p in (self.target,self.state,self.stage):
            p.mkdir(parents=True)
        self.stage.chmod(0o700)
        self.old={}
        self.new={}
        for name in updater.FILES:
            original=("old verified: "+name).encode()
            updated=("new source: "+name).encode()
            (self.target/name).write_bytes(original)
            (self.stage/name).write_bytes(updated)
            self.old[name]=sha(original)
            self.new[name]=sha(updated)
        self.patcher=mock.patch.multiple(updater,GATEWAY=self.target,PRIVATE=self.state)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.addCleanup(self.temp.cleanup)

    def test_atomic_upgrade_confined_to_payment_only(self):
        updater.upgrade(self.stage,self.old,self.new)
        for name in updater.FILES:
            self.assertEqual(updater.digest(self.target/name),self.new[name])
            self.assertEqual(updater.digest(self.stage/("backup-"+name)),self.old[name])
        self.assertFalse((self.state/"enabled.flag").exists())

    def test_never_touch_running_payment_processing(self):
        (self.state/"enabled.flag").write_text("active")
        with self.assertRaisesRegex(RuntimeError,"real payments"):
            updater.upgrade(self.stage,self.old,self.new)
        for name in updater.FILES:
            self.assertEqual(updater.digest(self.target/name),self.old[name])

    def test_reject_changed_production_file(self):
        (self.target/"index.php").write_text("unreviewed modifications")
        with self.assertRaisesRegex(RuntimeError,"checksum"):
            updater.upgrade(self.stage,self.old,self.new)
        self.assertEqual(updater.digest(self.target/"bootstrap.php"),self.old["bootstrap.php"])

    def test_reject_symlinked_staging_file(self):
        (self.stage/"bootstrap.php").unlink()
        (self.stage/"bootstrap.php").symlink_to(self.target/"bootstrap.php")
        with self.assertRaisesRegex(RuntimeError,"Unsafe"):
            updater.upgrade(self.stage,self.old,self.new)

    def test_rollback_if_second_rename_fails(self):
        original_replace=updater.os.replace
        def fail_second(src,dst):
            if Path(dst).name=="bootstrap.php":
                raise OSError("simulated atomic rename failure")
            return original_replace(src,dst)
        with mock.patch.object(updater.os,"replace",side_effect=fail_second):
            with self.assertRaises(OSError):
                updater.upgrade(self.stage,self.old,self.new)
        for name in updater.FILES:
            self.assertEqual(updater.digest(self.target/name),self.old[name])


if __name__=="__main__":
    unittest.main()
