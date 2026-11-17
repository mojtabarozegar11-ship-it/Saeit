"""No-network C171 parser and owner-only UAPI admission regressions."""
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import factory_c171_passenger_uapi_readonly as m


def reply(data, status=1):
    return json.dumps({'apiversion':3,'module':'PassengerApps',
                       'func':'list_applications','result':{'status':status,'data':data}},
                      separators=(',',':')).encode()


class C171PrivateRegistryTests(unittest.TestCase):
    def test_01_empty_registry_is_not_live_identity(self):
        o=m.classify_uapi_json(reply([]))
        self.assertTrue(o['uapi_query_completed'])
        self.assertEqual(o['registered_apps'],0)
        self.assertFalse(o['live_database_identity_proven'])

    def test_02_registered_staging_app(self):
        o=m.classify_uapi_json(reply([
            {'domain':'mojplaywin.com','path':'/home/zomorod2/Saeit-staging','enabled':1}]))
        self.assertEqual(o['registered_apps'],1)
        self.assertEqual(o['target_domain_staging_paths'],1)
        self.assertEqual(o['staging_app_roots'],1)
        self.assertFalse(o['live_passenger_worker_identity_proven'])

    def test_03_registered_webroot_app(self):
        o=m.classify_uapi_json(reply([
            {'domain':'www.mojplaywin.com','path':'mojplaywin.com','enabled':1}]))
        self.assertEqual(o['target_domain_webroot_paths'],1)

    def test_04_registered_other_owner_app(self):
        o=m.classify_uapi_json(reply([
            {'domain':'zomorodmelal.ir','path':'/home/zomorod2/sitev4','enabled':0}]))
        self.assertEqual(o['target_domain_other_paths'],1)
        self.assertEqual(o['enabled_apps'],0)

    def test_05_registered_outside_home_is_not_verified(self):
        o=m.classify_uapi_json(reply([
            {'domain':'mojplaywin.com','path':'/etc/passenger-app','enabled':1}]))
        self.assertEqual(o['outside_owner_app_roots'],1)
        self.assertFalse(o['complete_media_scope_proven'])

    def test_06_dict_payload_supported_without_record_names(self):
        o=m.classify_uapi_json(reply({'SECRET_APPLICATION_NAME':{
            'domain':'mojplaywin.com','path':'Saeit-staging','enabled':'1'}}))
        self.assertEqual(o['staging_app_roots'],1)
        self.assertNotIn('SECRET_APPLICATION_NAME',str(o))

    def test_07_non_target_domain_not_claimed(self):
        o=m.classify_uapi_json(reply([
            {'domain':'elsewhere.example','path':'Saeit-staging','enabled':1}]))
        self.assertEqual(o['target_domain_registrations'],0)
        self.assertEqual(o['registered_apps'],1)

    def test_08_www_target_normalization(self):
        o=m.classify_uapi_json(reply([
            {'domain':'WWW.ZOMORODMELAL.IR.','path':'~/Saeit-staging','enabled':True}]))
        self.assertEqual(o['target_domain_registrations'],1)
        self.assertEqual(o['enabled_apps'],1)

    def test_09_unknown_path_stays_unverified(self):
        o=m.classify_uapi_json(reply([{'domain':'mojplaywin.com'}]))
        self.assertEqual(o['unverified_app_roots'],1)
        self.assertFalse(o['live_database_identity_proven'])

    def test_10_dotdot_owner_path_denied(self):
        o=m.classify_uapi_json(reply([
            {'domain':'mojplaywin.com','path':'mojplaywin.com/../Saeit-staging'}]))
        self.assertEqual(o['unverified_app_roots'],1)

    def test_11_backslash_path_denied(self):
        o=m.classify_uapi_json(reply([
            {'domain':'mojplaywin.com','path':r'mojplaywin.com\\wrong'}]))
        self.assertEqual(o['unverified_app_roots'],1)

    def test_12_invalid_non_string_domain_not_target(self):
        o=m.classify_uapi_json(reply([
            {'domain':{'private':'secret'},'path':'Saeit-staging'}]))
        self.assertEqual(o['target_domain_registrations'],0)

    def test_13_uapi_status_zero_fail_closed(self):
        o=m.classify_uapi_json(reply([],status=0))
        self.assertEqual(o['registry_status'],'api_unavailable_or_failed')
        self.assertFalse(o['uapi_query_completed'])

    def test_14_uapi_boolean_status_denied(self):
        o=m.classify_uapi_json(reply([],status=True))
        self.assertEqual(o['registry_status'],'api_unavailable_or_failed')

    def test_15_bad_json_fail_closed(self):
        o=m.classify_uapi_json(b'NOT_JSON')
        self.assertEqual(o['registry_status'],'invalid_provider_response')

    def test_16_duplicate_json_keys_denied(self):
        o=m.classify_uapi_json(b'{"result":{"status":1,"status":1,"data":[]}}')
        self.assertEqual(o['registry_status'],'invalid_provider_response')

    def test_17_no_result_denied(self):
        o=m.classify_uapi_json(b'{"data":[]}')
        self.assertEqual(o['registry_status'],'invalid_provider_response')

    def test_18_bad_data_type_denied(self):
        o=m.classify_uapi_json(reply('not-apps'))
        self.assertEqual(o['registry_status'],'app_list_invalid_or_over_limit')

    def test_19_bad_data_members_denied(self):
        o=m.classify_uapi_json(reply([{'path':'Saeit-staging'},'LEAK']))
        self.assertEqual(o['registry_status'],'app_list_invalid_or_over_limit')
        self.assertEqual(o['registered_apps'],0)

    def test_20_app_count_limit_denied(self):
        o=m.classify_uapi_json(reply([{}]*(m.MAX_APPS+1)))
        self.assertEqual(o['registry_status'],'app_list_invalid_or_over_limit')

    def test_21_oversize_json_denied(self):
        o=m.classify_uapi_json(b'x'*(m.MAX_JSON_BYTES+1))
        self.assertTrue(o['uapi_response_size_exceeded'])

    def test_22_non_utf8_json_denied(self):
        o=m.classify_uapi_json(b'\\xff')
        self.assertFalse(o['uapi_query_completed'])

    def test_23_secret_envvars_never_output(self):
        o=m.classify_uapi_json(reply([
            {'domain':'mojplaywin.com','path':'Saeit-staging',
             'envvars':{'DATABASE_PASSWORD':'DO_NOT_PRINT_PRIVATE_TOKEN'}}]))
        self.assertNotIn('DO_NOT_PRINT_PRIVATE_TOKEN',json.dumps(o))
        self.assertFalse(o['envvars_output'])

    def test_24_error_string_never_output(self):
        raw=b'{"result":{"status":0,"errors":["PRIVATE_PASSWORD"]}}'
        self.assertNotIn('PRIVATE_PASSWORD',json.dumps(m.classify_uapi_json(raw)))

    def test_25_command_allowlist_hard_gate(self):
        with self.assertRaisesRegex(ValueError,'UAPI_COMMAND_NOT_ALLOWLISTED'):
            m._bounded_run(['/usr/bin/uapi','--output=json','Mysql','something'])

    def test_26_command_timeout_bounds(self):
        with self.assertRaisesRegex(ValueError,'INVALID_TIMEOUT'):
            m._bounded_run(timeout=0)

    def test_27_owner_identity_required(self):
        with patch.object(m.pwd,'getpwuid',return_value=SimpleNamespace(pw_name='not_owner')):
            o=m.report()
        self.assertFalse(o['owner_verified'])
        self.assertEqual(o['registry_status'],'not_attempted')

    def test_28_report_success_sanitizes_original_response(self):
        with patch.object(m.pwd,'getpwuid',return_value=SimpleNamespace(pw_name=m.OWNER)):
            with patch.object(m,'_bounded_run',return_value=reply([
                {'path':'Saeit-staging','domain':'mojplaywin.com',
                 'envvars':{'API_KEY':'SECRET_NEVER_EXPOSED'}}])):
                o=m.report()
        self.assertTrue(o['owner_verified'])
        self.assertTrue(o['uapi_query_completed'])
        self.assertNotIn('SECRET_NEVER_EXPOSED',str(o))

    def test_29_timeout_sanitized(self):
        with patch.object(m.pwd,'getpwuid',return_value=SimpleNamespace(pw_name=m.OWNER)):
            with patch.object(m,'_bounded_run',side_effect=TimeoutError('SECRET')):
                o=m.report()
        self.assertTrue(o['uapi_timeout'])
        self.assertNotIn('SECRET',str(o))

    def test_30_oversize_sanitized(self):
        with patch.object(m.pwd,'getpwuid',return_value=SimpleNamespace(pw_name=m.OWNER)):
            with patch.object(m,'_bounded_run',side_effect=OverflowError('SECRET')):
                o=m.report()
        self.assertTrue(o['uapi_response_size_exceeded'])
        self.assertNotIn('SECRET',str(o))

    def test_31_unavailable_uapi_sanitized(self):
        with patch.object(m.pwd,'getpwuid',return_value=SimpleNamespace(pw_name=m.OWNER)):
            with patch.object(m,'_bounded_run',side_effect=OSError('SECRET')):
                o=m.report()
        self.assertEqual(o['registry_status'],'uapi_unavailable_or_failed')
        self.assertNotIn('SECRET',str(o))

    def test_32_enabled_count_does_not_claim_runtime(self):
        o=m.classify_uapi_json(reply([
            {'domain':'mojplaywin.com','path':'Saeit-staging','enabled':1},
            {'domain':'mojplaywin.com','path':'mojplaywin.com','enabled':1}]))
        self.assertEqual(o['enabled_apps'],2)
        self.assertTrue(o['registered_metadata_not_runtime_attestation'])
        self.assertFalse(o['current_backup_created'])


    def _private_root_fixture(self):
        td=tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        home=Path(td.name)/'owner'
        home.mkdir(mode=0o700)
        new=home/'site-production'
        new.mkdir(mode=0o700)
        return home,new

    def test_33_registry_root_metadata_confirmed(self):
        home,root=self._private_root_fixture()
        (root/'passenger_wsgi.py').write_text('application=None')
        (root/'manage.py').write_text('print(1)')
        (root/'media').mkdir(mode=0o700)
        (root/'uploads').mkdir(mode=0o700)
        with patch.object(m,'HOME',PurePosixPath(home)):
            r=m._registered_root_metadata_census(reply([{'path':'site-production'}]),os.geteuid())
        self.assertTrue(r['registered_root_census_attempted'])
        self.assertEqual(r['registered_root_secure_dirs'],1)
        self.assertEqual(r['registered_root_wsgi_metadata'],1)
        self.assertEqual(r['registered_root_manage_metadata'],1)
        self.assertEqual(r['registered_root_media_metadata'],1)
        self.assertEqual(r['registered_root_uploads_metadata'],1)

    def test_34_missing_registered_root_not_proven(self):
        home,root=self._private_root_fixture()
        with patch.object(m,'HOME',PurePosixPath(home)):
            r=m._registered_root_metadata_census(reply([{'path':'not_created'}]),os.geteuid())
        self.assertEqual(r['registered_root_unverified_dirs'],1)
        self.assertEqual(r['registered_root_secure_dirs'],0)

    def test_35_registered_root_symlink_denied(self):
        home,root=self._private_root_fixture()
        (home/'link').symlink_to(root)
        with patch.object(m,'HOME',PurePosixPath(home)):
            r=m._registered_root_metadata_census(reply([{'path':'link'}]),os.geteuid())
        self.assertEqual(r['registered_root_unverified_dirs'],1)

    def test_36_group_writable_registered_root_denied(self):
        home,root=self._private_root_fixture()
        root.chmod(0o770)
        with patch.object(m,'HOME',PurePosixPath(home)):
            r=m._registered_root_metadata_census(reply([{'path':'site-production'}]),os.geteuid())
        self.assertEqual(r['registered_root_unverified_dirs'],1)

    def test_37_symlinked_media_never_counted(self):
        home,root=self._private_root_fixture()
        (root/'media').symlink_to(home)
        with patch.object(m,'HOME',PurePosixPath(home)):
            r=m._registered_root_metadata_census(reply([{'path':'site-production'}]),os.geteuid())
        self.assertEqual(r['registered_root_secure_dirs'],1)
        self.assertEqual(r['registered_root_media_metadata'],0)

    def test_38_non_owner_registered_root_denied(self):
        home,root=self._private_root_fixture()
        with patch.object(m,'HOME',PurePosixPath(home)):
            r=m._registered_root_metadata_census(reply([{'path':'site-production'}]),os.geteuid()+10000)
        self.assertEqual(r['registered_root_unverified_dirs'],1)

    def test_39_outside_home_registered_root_denied(self):
        home,root=self._private_root_fixture()
        with patch.object(m,'HOME',PurePosixPath(home)):
            r=m._registered_root_metadata_census(reply([{'path':'/etc'}]),os.geteuid())
        self.assertEqual(r['registered_root_unverified_dirs'],1)

    def test_40_provider_api_failure_no_metadata_census(self):
        home,root=self._private_root_fixture()
        with patch.object(m,'HOME',PurePosixPath(home)):
            r=m._registered_root_metadata_census(reply([],status=0),os.geteuid())
        self.assertFalse(r['registered_root_census_attempted'])

    def test_41_no_file_contents_read_during_root_census(self):
        home,root=self._private_root_fixture()
        (root/'passenger_wsgi.py').write_text('do_not_open')
        with patch.object(m,'HOME',PurePosixPath(home)):
            with patch('builtins.open',side_effect=AssertionError('CONTENTS_MUST_NOT_BE_READ')):
                r=m._registered_root_metadata_census(reply([{'path':'site-production'}]),os.geteuid())
        self.assertEqual(r['registered_root_wsgi_metadata'],1)

    def test_42_report_with_owner_root_metadata_no_path_leak(self):
        home,root=self._private_root_fixture()
        with patch.object(m,'HOME',PurePosixPath(home)):
            with patch.object(m.pwd,'getpwuid',return_value=SimpleNamespace(pw_name=m.OWNER)):
                with patch.object(m,'_bounded_run',return_value=reply([{
                    'domain':'mojplaywin.com','path':'site-production',
                    'envvars':{'SECRET':'VERY_PRIVATE_VALUE'}}])):
                    o=m.report()
        self.assertEqual(o['registered_root_secure_dirs'],1)
        self.assertNotIn(str(home),str(o))
        self.assertNotIn('VERY_PRIVATE_VALUE',str(o))
        self.assertFalse(o['live_database_identity_proven'])


if __name__ == '__main__':
    unittest.main()
