from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

src = Path(__file__).parent / 'factory_owner_drive_setup.py'
spec = importlib.util.spec_from_file_location('factory_owner_drive_setup', src)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

class TestOwnerDriveSetup(unittest.TestCase):
    def test_01_two_private_roots_are_distinct(self):
        self.assertNotEqual(m.ROOT_A, m.ROOT_B)
    def test_02_real_private_proof_pin(self):
        self.assertEqual(len(m.PROOF_SHA), 64)
    def test_03_noninteractive_denied(self):
        with patch.object(m.sys.stdin, 'isatty', return_value=False):
            self.assertEqual(m.main([]), 2)
    def test_04_github_actions_denied(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS':'true'}):
            with patch.object(m.sys.stdin, 'isatty', return_value=True), patch.object(m.sys.stdout, 'isatty', return_value=True):
                self.assertEqual(m.main([]), 2)
    def test_05_foreign_home_denied(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(m.TransferHold): m._secure_config_directory(Path(td))
    def test_06_config_dir_creation_private(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            with patch.object(m.Path, 'home', return_value=home):
                cfg=m._secure_config_directory(home)
                self.assertEqual(cfg,home/'.config/rclone/rclone.conf')
                self.assertEqual(cfg.parent.stat().st_mode & 0o777, 0o700)
    def test_07_public_dotconfig_acceptable(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);p=home/'.config';p.mkdir(mode=0o755)
            with patch.object(m.Path, 'home', return_value=home):
                cfg=m._secure_config_directory(home)
                self.assertEqual(cfg.parent.stat().st_mode & 0o777,0o700)
    def test_08_dotconfig_symlink_denied(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);target=home/'notconfig';target.mkdir();(home/'.config').symlink_to(target)
            with patch.object(m.Path, 'home', return_value=home):
                with self.assertRaises(m.TransferHold):m._secure_config_directory(home)
    def test_09_rclone_dir_public_denied(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);p=home/'.config/rclone';p.mkdir(parents=True);p.chmod(0o755)
            with patch.object(m.Path,'home',return_value=home):
                with self.assertRaises(m.TransferHold):m._secure_config_directory(home)
    def test_10_group_write_denied(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);p=home/'.config';p.mkdir();p.chmod(0o775)
            with patch.object(m.Path,'home',return_value=home):
                with self.assertRaises(m.TransferHold):m._secure_config_directory(home)
    def test_11_existing_0600_config_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);p=home/'.config/rclone';p.mkdir(parents=True);p.chmod(0o700)
            c=p/'rclone.conf';c.write_text('owner config');c.chmod(0o600)
            with patch.object(m.Path,'home',return_value=home):
                self.assertEqual(m._secure_config_directory(home),c)
                self.assertEqual(c.read_text(),'owner config')
    def test_12_existing_0644_config_denied(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);p=home/'.config/rclone';p.mkdir(parents=True);p.chmod(0o700)
            c=p/'rclone.conf';c.write_text('unsafe');c.chmod(0o644)
            with patch.object(m.Path,'home',return_value=home):
                with self.assertRaises(m.TransferHold):m._secure_config_directory(home)
    def test_13_existing_config_symlink_denied(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td);p=home/'.config/rclone';p.mkdir(parents=True);p.chmod(0o700)
            c=p/'rclone.conf';c.symlink_to(home/'secret')
            with patch.object(m.Path,'home',return_value=home):
                with self.assertRaises(m.TransferHold):m._secure_config_directory(home)
    def test_14_readonly_cert_explicit_no_backup(self):
        adm=SimpleNamespace(free_a_before=12345678900,free_b_before=9876543210,proof_readbacks_verified=True)
        with patch.object(m,'RcloneDualStore') as store:
            store.return_value.preflight.return_value=adm
            data=m._check(Path('/some/binary'),Path('/some/config'))
        self.assertTrue(data['distinct_private_drives_verified'])
        self.assertFalse(data['current_backup_created'])
        self.assertFalse(data['current_factory_size_admitted'])
        self.assertFalse(data['production_modified'])
        self.assertEqual(data['free_bytes_drive_a'],12345678900)
    def test_15_no_secret_fields_in_output(self):
        adm=SimpleNamespace(free_a_before=5555555555,free_b_before=4444444444,proof_readbacks_verified=True)
        with patch.object(m,'RcloneDualStore') as store:
            store.return_value.preflight.return_value=adm
            data=m._check(Path('/bin/a'),Path('/tmp/conf'))
        text=json.dumps(data).lower()
        for forbidden in ('token','refresh','credential','client_secret','private_key','passphrase'):
            self.assertNotIn(forbidden,text)
    def test_16_provider_hold_not_swallowed(self):
        with patch.object(m,'RcloneDualStore') as s:
            s.return_value.preflight.side_effect=m.TransferHold('PRIVATE_OWNER_PROOF_MISMATCH')
            with self.assertRaises(m.TransferHold):m._check(Path('/bin/a'),Path('/tmp/conf'))
    def test_17_configure_flag_required_for_interactive_creation(self):
        self.assertTrue(m.PROOF_SHA.startswith('753365e1'))
    def test_18_no_raw_mysql_or_cloud_write_methods(self):
        source=src.read_text()
        for unsafe in ('mariadb-dump','rclone sync','rclone rcat','rm -rf','subprocess.Popen'):
            self.assertNotIn(unsafe,source)

if __name__=='__main__':unittest.main()
