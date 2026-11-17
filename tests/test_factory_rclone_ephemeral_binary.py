"""Pure offline test cases for pinned, ephemeral release verification."""
from __future__ import annotations
import hashlib
import io
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from factory_rclone_ephemeral_binary import (
    AdmissionHold, ZIP_ENTRY, MAX_ARCHIVE_BYTES, MAX_BINARY_BYTES,
    ARCHIVE_SHA256, ARCHIVE_BYTES, ARCHIVE_URL,
    _verify_zip, install_verified_archive, verify_binary_version, provision_verified_rclone,
)


def make_zip(entry=ZIP_ENTRY, content=b'ELF mock placeholder', extra=()):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        info=zipfile.ZipInfo(entry)
        info.external_attr=(stat.S_IFREG|0o755)<<16
        z.writestr(info,content)
        for path in extra: z.writestr(path,b'x')
    return buf.getvalue()


class TestEphemeralRclone(unittest.TestCase):
    def test_01_version_pinned(self):
        self.assertEqual('v1.76.0',__import__('factory_rclone_ephemeral_binary').VERSION)
    def test_02_download_is_official_versioned_asset(self):
        self.assertTrue(ARCHIVE_URL.startswith('https://github.com/rclone/rclone/releases/download/v1.76.0/'))
    def test_03_asset_size_pinned(self):
        self.assertEqual(ARCHIVE_BYTES,32194302)
    def test_04_asset_digest_pinned(self):
        self.assertEqual(ARCHIVE_SHA256,'b00f00b3266c3764413afe599d3ec316f6f43b3e0ea8a0bc1d186d2133e46df7')
    def test_05_synthetic_zip_digest_accepted_when_explicitly_pinned(self):
        b=make_zip()
        with _verify_zip(b,hashlib.sha256(b).hexdigest()) as z:
            self.assertEqual(z.read(ZIP_ENTRY),b'ELF mock placeholder')
    def test_06_tampered_archive_rejected(self):
        b=make_zip()
        with self.assertRaisesRegex(AdmissionHold,'RELEASE_SHA256_MISMATCH'):
            _verify_zip(b,hashlib.sha256(b'not this').hexdigest())
    def test_07_missing_executable_rejected(self):
        b=make_zip('rclone-v1.76.0-linux-amd64/not-rclone')
        with self.assertRaisesRegex(AdmissionHold,'UNEXPECTED_RELEASE_ZIP_LAYOUT'):
            _verify_zip(b,hashlib.sha256(b).hexdigest())
    def test_08_parent_traversal_rejected(self):
        b=make_zip(extra=['rclone-v1.76.0-linux-amd64/../../escape'])
        with self.assertRaisesRegex(AdmissionHold,'ZIP_PATH_UNSAFE'):
            _verify_zip(b,hashlib.sha256(b).hexdigest())
    def test_09_absolute_path_rejected(self):
        b=make_zip(extra=['/root/secret'])
        with self.assertRaisesRegex(AdmissionHold,'ZIP_PATH_UNSAFE'):
            _verify_zip(b,hashlib.sha256(b).hexdigest())
    def test_10_duplicate_entry_rejected(self):
        b=make_zip(extra=[ZIP_ENTRY])
        with self.assertRaisesRegex(AdmissionHold,'UNEXPECTED_RELEASE_ZIP_LAYOUT'):
            _verify_zip(b,hashlib.sha256(b).hexdigest())
    def test_11_oversized_archive_rejected(self):
        with self.assertRaisesRegex(AdmissionHold,'ARCHIVE_BOUND_FAIL'):
            _verify_zip(b'a'*(MAX_ARCHIVE_BYTES+1),hashlib.sha256(b'a').hexdigest())
    def test_12_bad_zip_rejected(self):
        b=b'totally-not-zip'
        with self.assertRaisesRegex(AdmissionHold,'INVALID_RELEASE_ARCHIVE'):
            _verify_zip(b,hashlib.sha256(b).hexdigest())
    def test_13_installed_mock_is_owner_only_and_exact_bytes(self):
        b=make_zip(); h=hashlib.sha256(b).hexdigest()
        with tempfile.TemporaryDirectory() as t:
            p=install_verified_archive(b,Path(t),expected_sha=h)
            self.assertEqual(p.read_bytes(),b'ELF mock placeholder')
            self.assertEqual(p.stat().st_mode & 0o777,0o700)
    def test_14_duplicate_install_rejected_and_original_untouched(self):
        b=make_zip(); h=hashlib.sha256(b).hexdigest()
        with tempfile.TemporaryDirectory() as t:
            p=install_verified_archive(b,Path(t),expected_sha=h)
            with self.assertRaisesRegex(AdmissionHold,'NO_OVERWRITE'):
                install_verified_archive(b,Path(t),expected_sha=h)
            self.assertEqual(p.read_bytes(),b'ELF mock placeholder')
    def test_15_executable_is_not_shell_invoked(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'rclone';p.write_bytes(b'invalid-executable');p.chmod(0o700)
            self.assertFalse(verify_binary_version(p))
    def test_16_private_temp_root_required(self):
        b=make_zip();h=hashlib.sha256(b).hexdigest()
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);p.chmod(0o755)
            with self.assertRaisesRegex(AdmissionHold,'TEMP_ROOT_NOT_PRIVATE'):
                install_verified_archive(b,p,expected_sha=h)
    def test_17_bad_digest_pin_rejected(self):
        b=make_zip()
        with self.assertRaisesRegex(AdmissionHold,'INVALID_DIGEST_PIN'):
            _verify_zip(b,'not-a-sha')
    def test_18_blob_limit_is_bounded(self):
        self.assertLessEqual(MAX_ARCHIVE_BYTES,34*1024*1024)
        self.assertLessEqual(MAX_BINARY_BYTES,140*1024*1024)
    def test_19_context_cleanup_success(self):
        blob=make_zip()
        with tempfile.TemporaryDirectory() as t:
            with patch('factory_rclone_ephemeral_binary.install_verified_archive') as install, patch(
                'factory_rclone_ephemeral_binary.verify_binary_version',return_value=True):
                install.side_effect=lambda raw,dest: (dest/'rclone')
                with provision_verified_rclone(Path(t),downloader=lambda:blob) as p:
                    self.assertTrue(p.parent.is_dir())
                    assert p.parent.parent == Path(t)
                self.assertFalse(p.parent.exists())
    def test_20_context_cleanup_after_invalid_version(self):
        blob=make_zip()
        with tempfile.TemporaryDirectory() as t:
            with patch('factory_rclone_ephemeral_binary.install_verified_archive') as install, patch(
                'factory_rclone_ephemeral_binary.verify_binary_version',return_value=False):
                install.side_effect=lambda raw,dest:(dest/'rclone')
                with self.assertRaisesRegex(AdmissionHold,'RCLONE_VERSION_MISMATCH'):
                    with provision_verified_rclone(Path(t),downloader=lambda:blob): pass
            self.assertFalse(list(Path(t).iterdir()))
    def test_21_no_oauth_key_default_usage(self):
        from factory_rclone_ephemeral_binary import main
        self.assertFalse('rclone config' in main.__code__.co_names)

if __name__=='__main__':unittest.main()
