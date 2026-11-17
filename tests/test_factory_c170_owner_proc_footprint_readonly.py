import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import factory_c170_owner_proc_footprint_readonly as m


class C170OfflineTests(unittest.TestCase):
    def test_01_no_owner_never_claims_worker(self):
        with patch.object(m.os, 'geteuid', return_value=os.geteuid()), patch.object(m.pwd, 'getpwuid', side_effect=KeyError):
            x=m.scan();self.assertFalse(x['owner_verified']);self.assertFalse(x['passenger_live_db_identity_proven'])
    def test_02_no_pid_dir_no_candidates(self):
        with tempfile.TemporaryDirectory() as d:
            x=m.scan(Path(d),os.geteuid());self.assertTrue(x['scan_completed']);self.assertEqual(x['candidate_processes_observed'],0)
    def test_03_unavailable_proc_fails_closed(self):
        x=m.scan(Path('/this-proc-path-c170-must-not-exist'),os.geteuid());self.assertFalse(x['scan_completed']);self.assertTrue(x['proc_error_occurred'])
    def test_04_passenger_comm(self):self.assertEqual(m._process_type(b'Passenger\n'),'passenger_like')
    def test_05_python_comm(self):self.assertEqual(m._process_type(b'python3.11\n'),'python_like')
    def test_06_other_comm(self):self.assertEqual(m._process_type(b'bash\n'),'other')
    def test_07_huge_comm_rejected(self):self.assertEqual(m._process_type(b'X'*65),'unknown')
    def test_08_bad_bytes_rejected(self):self.assertEqual(m._process_type(b'\xff'),'unknown')
    def test_09_staging_cwd_is_hint(self):self.assertEqual(m._cwd_class('/home/zomorod2/Saeit-staging/worker'),'staging_cwd_hint')
    def test_10_webroot_cwd_is_hint(self):self.assertEqual(m._cwd_class('/home/zomorod2/mojplaywin.com'),'webroot_cwd_hint')
    def test_11_owner_other_cwd(self):self.assertEqual(m._cwd_class('/home/zomorod2/another-app'),'other_owner_cwd_hint')
    def test_12_outside_owner_cwd(self):self.assertEqual(m._cwd_class('/var/www'),'outside_owner_home_cwd_hint')
    def test_13_relative_cwd_unverified(self):self.assertEqual(m._cwd_class('home/zomorod2'),'unverified')
    def test_14_dotdot_cwd_unverified(self):self.assertEqual(m._cwd_class('/home/zomorod2/../root'),'unverified')
    def test_15_never_false_prove_identity(self):
        x=m._report_stub()
        for k in ('passenger_live_db_identity_proven','worker_code_identity_proven','complete_media_scope_proven','mysql_connected','customer_contents_read','cmdline_read','environ_read','backup_created','production_modified'):
            self.assertFalse(x[k],k)
    def test_16_one_real_fake_proc_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'12345';p.mkdir();(p/'comm').write_bytes(b'python3\n');(p/'cwd').symlink_to('/home/zomorod2/Saeit-staging')
            x=m.scan(Path(d),os.geteuid());self.assertTrue(x['scan_completed']);self.assertEqual(x['candidate_staging_cwd_hints'],1);self.assertFalse(x['passenger_live_db_identity_proven'])
    def test_17_non_candidate_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'2468';p.mkdir();(p/'comm').write_bytes(b'bash\n');(p/'cwd').symlink_to('/home/zomorod2/Saeit-staging')
            x=m.scan(Path(d),os.geteuid());self.assertEqual(x['candidate_processes_observed'],0)
    def test_18_malformed_pid_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'123abc';p.mkdir();(p/'comm').write_bytes(b'python\n');(p/'cwd').symlink_to('/home/zomorod2/Saeit-staging')
            x=m.scan(Path(d),os.geteuid());self.assertEqual(x['candidate_processes_observed'],0)
    def test_19_exited_proc_does_not_claim(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'321';p.mkdir();(p/'comm').write_bytes(b'python\n')
            x=m.scan(Path(d),os.geteuid());self.assertEqual(x['candidate_staging_cwd_hints'],0)
    def test_20_report_json_no_sensitive_paths(self):
        with tempfile.TemporaryDirectory() as d:
            v=json.dumps(m.scan(Path(d),os.geteuid()))
            self.assertNotIn('home/zomorod2',v)
            self.assertNotIn('password',v.lower())
            self.assertNotIn('token',v.lower())

if __name__=='__main__':unittest.main()
