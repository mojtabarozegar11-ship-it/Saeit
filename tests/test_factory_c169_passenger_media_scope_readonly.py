"""Offline, no owner host or customer files; bounded read-only C169 invariants."""
import importlib.util, pathlib, tempfile, os, unittest
p=pathlib.Path(__file__).resolve().parents[1]/'scripts/factory_c169_passenger_media_scope_readonly.py'
s=importlib.util.spec_from_file_location('factory_c169',p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class C169Safety(unittest.TestCase):
    def test_01_empty_wsgi(self):self.assertFalse(m.wsgi_signals(b'')['parsed'])
    def test_02_too_large_wsgi(self):self.assertFalse(m.wsgi_signals(b'x'*40000)['parsed'])
    def test_03_invalid_utf8(self):self.assertFalse(m.wsgi_signals(b'\xff')['parsed'])
    def test_04_invalid_python(self):self.assertFalse(m.wsgi_signals(b'def ...')['parsed'])
    def test_05_deep_nesting(self):self.assertFalse(m.wsgi_signals(b'x=('+b'('*132+b'1')['parsed'])
    def test_06_comment_cannot_spoof_staging(self):self.assertFalse(m.wsgi_signals(b'# /home/zomorod2/Saeit-staging\napplication=1')['staging_literal'])
    def test_07_string_constant_can_signal_staging(self):self.assertTrue(m.wsgi_signals(b'x="/home/zomorod2/Saeit-staging"\napplication=1')['staging_literal'])
    def test_08_application_assignment_detected(self):self.assertTrue(m.wsgi_signals(b'application=1')['application_declared'])
    def test_09_no_application_assignment(self):self.assertFalse(m.wsgi_signals(b'x=1')['application_declared'])
    def test_10_django_symbol_detected(self):self.assertTrue(m.wsgi_signals(b'application=get_wsgi_application()')['wsgi_loader_symbol_present'])
    def test_11_wrong_django_settings_literal(self):self.assertFalse(m.wsgi_signals(b'x="config.other"')['django_settings_literal'])
    def test_12_true_django_settings_literal(self):self.assertTrue(m.wsgi_signals(b'x="config.settings"')['django_settings_literal'])
    def test_13_default_flags_not_live_proof(self):self.assertFalse(m.storage_flags(None)['production_worker_db_identity_verified'])
    def test_14_default_flags_not_complete_media(self):self.assertFalse(m.storage_flags(None)['app_media_complete'])
    def test_15_config_missing_media(self):
        class C:DATABASES={'default':{'ENGINE':'django.db.backends.mysql','NAME':'db'}};STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'}};MEDIA_ROOT=''
        x=m.storage_flags(C);self.assertEqual(x['media_root_state'],'not_configured');self.assertEqual(x['database_backend'],'mysql');self.assertEqual(x['file_backend'],'filesystem')
    def test_16_other_database(self):
        class C:DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':'db'}};STORAGES={};MEDIA_ROOT=''
        self.assertEqual(m.storage_flags(C)['database_backend'],'other')
    def test_17_relative_media_hold(self):
        class C:DATABASES={};STORAGES={};MEDIA_ROOT='uploads'
        self.assertEqual(m.storage_flags(C)['media_root_state'],'relative_unverified')
    def test_18_external_media_hold(self):
        class C:DATABASES={};STORAGES={};MEDIA_ROOT='/tmp/media'
        self.assertEqual(m.storage_flags(C)['media_root_state'],'outside_owner_home')
    def test_19_candidate_outside_home(self):self.assertEqual(m.fixed_candidate_status(pathlib.Path('/tmp/forbidden'),os.getuid())['state'],'outside_fixed_home')
    def test_20_missing_candidate_does_not_claim_backup(self):self.assertFalse(m.fixed_candidate_status_stub()['recursive_scope_proven'])
    def test_21_missing_candidate_does_not_read_file_content(self):self.assertFalse(m.fixed_candidate_status_stub()['file_content_read'])
    def test_22_unique_fixed_candidate_labels(self):self.assertEqual(len(m.CANDIDATES),len(set(m.CANDIDATES)))
    def test_23_status_six_fixed_candidates(self):self.assertEqual(len(m.CANDIDATES),6)
    def test_24_root_owner_path_policy(self):self.assertTrue(all(m.HOME in p.parents for p in m.CANDIDATES.values()))
    def test_25_no_network_or_exec_imports(self):
        src=p.read_text(); self.assertNotIn('import requests',src);self.assertNotIn('import subprocess',src);self.assertNotIn('exec(',src)
    def test_26_release_flag_false(self):
        # Verify checked-in source defaults cannot misrepresent live worker.
        src=p.read_text();self.assertIn("'production_release_authorized':False",src)
    def test_27_no_synthetic_report_called_proof(self):self.assertFalse(m.storage_flags(None)['app_media_complete'])

if __name__=='__main__':unittest.main()
