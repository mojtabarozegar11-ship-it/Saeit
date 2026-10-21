"""Synthetic-only validation of read-only backup metadata diagnostics."""
import io
import tarfile
import unittest
from unittest.mock import patch

from tools.moj_commerce_v12_passenger_backup_diagnostic import (classify_archive, passenger, classify_absolute_link_target)


def synthetic_archive():
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w') as tar:
        for name, payload in [
            ('Saeit-staging/data.bin', b'abc'),
            ('mojplaywin.com/index.html', b'html'),
        ]:
            item = tarfile.TarInfo(name)
            item.size = len(payload)
            tar.addfile(item, io.BytesIO(payload))
        for name, target in [
            ('Saeit-staging/venv/python', '/usr/local/bin/python3'),
            ('mojplaywin.com/inside', 'index.html'),
            ('mojplaywin.com/outside', '../../etc/passwd'),
        ]:
            item = tarfile.TarInfo(name)
            item.type = tarfile.SYMTYPE
            item.linkname = target
            tar.addfile(item)
        link = tarfile.TarInfo('mojplaywin.com/dangling-hardlink')
        link.type = tarfile.LNKTYPE
        link.linkname = 'mojplaywin.com/missing'
        tar.addfile(link)
    out.seek(0)
    return out


class DiagnosticTests(unittest.TestCase):
    def test_safe_aggregate_only_no_extraction(self):
        report = classify_archive(synthetic_archive())
        self.assertEqual(report['classification'], 'MOJ_COMMERCE_V12_BACKUP_TAR_METADATA_ONLY')
        self.assertEqual(report['counters']['regular_files'], 2)
        self.assertEqual(report['counters']['absolute_link_targets'], 1)
        self.assertEqual(report['counters']['relative_link_escape'], 1)
        self.assertEqual(report['counters']['missing_hardlink_targets'], 1)
        self.assertTrue(report['source_roots_present'])
        self.assertFalse(report['archive_restored'])
        self.assertFalse(report['release_permitted'])
        self.assertNotIn('/usr/local', str(report))
        self.assertNotIn('etc/passwd', str(report))

    def test_absolute_link_bucket_no_target_leakage(self):
        self.assertEqual(classify_absolute_link_target(
            '/home/zomorod2/Saeit-staging/config/wsgi.py'), 'within_archive_roots')
        self.assertEqual(classify_absolute_link_target(
            '/home/zomorod2/mojplaywin.com/assets/a.png'), 'within_archive_roots')
        self.assertEqual(classify_absolute_link_target(
            '/opt/alt/python311/bin/python3.11'), 'runtime_dependency')
        for path in ('/home/zomorod2/Saeit-staging/../../etc/passwd',
                     '/home/zomorod2/extra_private/file',
                     '/home/zomorod2/Saeit-staging-evil/file'):
            with self.subTest():
                self.assertEqual(classify_absolute_link_target(path), 'tenant_unbacked')
        self.assertEqual(classify_absolute_link_target('/home/otheruser/file'),
                         'other_account_home')
        self.assertEqual(classify_absolute_link_target('/etc/shadow'), 'external_other')
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as tar:
            for name, target in [
                ('Saeit-staging/venv/python', '/opt/alt/python311/bin/python3.11'),
                ('Saeit-staging/mirror', '/home/zomorod2/Saeit-staging/data.bin'),
                ('mojplaywin.com/etc', '/etc/shadow'),
            ]:
                item = tarfile.TarInfo(name)
                item.type = tarfile.SYMTYPE
                item.linkname = target
                tar.addfile(item)
            for name in ('Saeit-staging/data.bin', 'mojplaywin.com/index.html'):
                item = tarfile.TarInfo(name)
                item.size = 1
                tar.addfile(item, io.BytesIO(b'x'))
        archive.seek(0)
        result = classify_archive(archive)['counters']
        self.assertEqual(result['absolute_link_targets'], 3)
        self.assertEqual(result['absolute_within_archive_roots'], 1)
        self.assertEqual(result['absolute_runtime_dependency'], 1)
        self.assertEqual(result['absolute_external_other'], 1)
        self.assertEqual(result['absolute_tenant_unbacked'], 0)
        self.assertEqual(result['absolute_other_account_home'], 0)
        self.assertNotIn('etc/shadow', str(result))
        self.assertNotIn('python311', str(result))

    def test_passenger_source_probe_never_claims_runtime_proven(self):
        report = passenger()
        self.assertFalse(report['passenger_worker_environment_proven'])
        self.assertFalse(report['passenger_runtime_database_proven'])
        self.assertFalse(report['release_permitted'])


if __name__ == '__main__':
    unittest.main()
