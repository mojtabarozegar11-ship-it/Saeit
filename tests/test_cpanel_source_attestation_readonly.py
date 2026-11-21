"""Offline tests for the strictly read-only live cPanel source attestation.

Runs with 'python -m unittest discover -s tests -p test_cpanel_source_attestation_readonly.py -v'.
Fixture files live only under the OS temporary test directory. No SSH,
mail, payment, production I/O, Django imports or real hosting credentials.
"""
import os
import pathlib
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts import mpw_cpanel_source_attestation_readonly as att


class CpanelReadOnlyAttestationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = pathlib.Path(self.tmp.name)
        self.app = self.base / "Saeit-staging"
        self.site = self.base / "mojplaywin.com"
        self.app.mkdir()
        self.site.mkdir()
        for rel, markers in att.SOURCE_MARKERS.items():
            path = self.app / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(markers.values()) + "\n", encoding="utf8")
        self.wsgi = self.site / "passenger_wsgi.py"
        self.wsgi.write_text("Saeit-staging\n", encoding="utf8")
        self.patches = [
            patch.object(att, "HOME", self.base),
            patch.object(att, "APP", self.app),
            patch.object(att, "SITE", self.site),
            patch.object(att, "WSGI", self.wsgi),
            patch.object(att.pwd, "getpwuid", return_value=types.SimpleNamespace(pw_name="zomorod2")),
        ]
        for entry in self.patches:
            entry.start()
            self.addCleanup(entry.stop)

    def test_01_complete_fixture_is_measured(self):
        answer = att.run()
        self.assertFalse(answer["blockers"])
        self.assertEqual(len(answer["observations"]), len(att.SOURCE_MARKERS)+1)

    def test_02_guards_never_authorize_deployment(self):
        result = att.run()
        self.assertIs(result["production_release_authorized"], False)
        self.assertIs(result["paid_transfer_executed"], False)
        self.assertIs(result["mail_sent"], False)

    def test_03_never_reads_customer_database(self):
        result = att.run()
        self.assertIs(result["db_connected"], False)
        self.assertIs(result["customer_data_read"], False)

    def test_04_no_file_modified(self):
        paths = [self.app / p for p in att.SOURCE_MARKERS]
        paths.append(self.wsgi)
        before = [(p.stat().st_size, p.stat().st_mtime_ns) for p in paths]
        result = att.run()
        after = [(p.stat().st_size, p.stat().st_mtime_ns) for p in paths]
        self.assertEqual(before, after)
        self.assertIs(result["files_modified"], False)

    def test_05_source_hash_is_hex_sha256(self):
        result = att.run()
        key = "services/mpw_trx_guest_delivery.py"
        value = result["observations"][key]
        self.assertEqual(len(value["sha256"]), 64)
        self.assertGreater(value["bytes"], 0)

    def test_06_markers_must_all_be_true_for_complete_claim(self):
        target = self.app / "services/mpw_trx_guest_delivery.py"
        target.write_text("incomplete module\n", encoding="utf8")
        result = att.run()
        self.assertIn("SOME_SOURCE_CAPABILITIES_NOT_INSTALLED", result["blockers"])

    def test_07_missing_source_is_explicit_blocker(self):
        (self.app / "services/mpw_trx_guest_delivery.py").unlink()
        result = att.run()
        self.assertIn("SOURCE_MISSING:services/mpw_trx_guest_delivery.py", result["blockers"])

    def test_08_missing_wsgi_holds_attestation(self):
        self.wsgi.unlink()
        self.assertIn("PASSENGER_ENTRY_UNVERIFIED", att.run()["blockers"])

    def test_09_wrong_account_is_denied(self):
        with patch.object(att.pwd, "getpwuid", return_value=types.SimpleNamespace(pw_name="other")):
            answer = att.run()
        self.assertEqual(answer["blockers"], ["WRONG_CPANEL_USER"])

    def test_10_symlinked_app_root_denied(self):
        real = self.base / "real"
        real.mkdir()
        import shutil
        shutil.rmtree(self.app)
        self.app.symlink_to(real)
        self.assertIn("CPANEL_ROOT_OR_SITE_UNTRUSTED", att.run()["blockers"])

    def test_11_symlinked_source_file_denied(self):
        target = self.app / "services/mpw_trx_guest_delivery.py"
        target.unlink()
        other = self.app / "services/hidden.py"
        other.write_text("sensitive\n")
        target.symlink_to(other)
        result = att.run()
        self.assertEqual(result["observations"]["services/mpw_trx_guest_delivery.py"]["status"], "held")

    def test_12_symlinked_source_directory_denied(self):
        import shutil
        source_dir = self.app / "services"
        shutil.rmtree(source_dir)
        destination = self.base / "untrusted"
        destination.mkdir()
        source_dir.symlink_to(destination)
        result = att.run()
        self.assertIn("SOURCE_PARENT_UNTRUSTED:services/mpw_trx_guest_delivery.py", result["blockers"])

    def test_13_zero_length_file_rejected(self):
        target = self.app / "services/mpw_trx_guest_delivery.py"
        target.write_bytes(b"")
        self.assertEqual(att.run()["observations"]["services/mpw_trx_guest_delivery.py"]["status"], "held")

    def test_14_oversized_file_rejected(self):
        target = self.app / "services/mpw_trx_guest_delivery.py"
        with target.open("wb") as fp:
            fp.truncate(att.MAX_SOURCE_BYTES + 1)
        self.assertEqual(att.run()["observations"]["services/mpw_trx_guest_delivery.py"]["status"], "held")

    def test_15_wsgi_wrong_root_detected_as_missing_capability(self):
        self.wsgi.write_text("Some other root\n", encoding="utf8")
        self.assertIn("SOME_SOURCE_CAPABILITIES_NOT_INSTALLED", att.run()["blockers"])

    def test_16_success_result_has_no_source_contents(self):
        result = att.run()
        text = str(result)
        self.assertNotIn("TOKEN_SALT =", text)
        self.assertNotIn("support@mojplaywin.com", text)
        self.assertNotIn("sensitive", text)

    def test_17_only_expected_paths_are_inspected(self):
        expected = set(att.SOURCE_MARKERS)
        expected.add("passenger_wsgi.py")
        self.assertEqual(set(att.run()["observations"]), expected)

    def test_18_owner_metadata_required(self):
        # Use a mocked non-owner uid for one open, not real chmod/chown.
        file_path = self.app / "services/mpw_trx_guest_delivery.py"
        real_fstat = att.os.fstat
        def wrong_owner(fd):
            obj = real_fstat(fd)
            if pathlib.Path("/proc/self/fd/" + str(fd)).resolve() == file_path:
                return types.SimpleNamespace(**dict((k, getattr(obj, k)) for k in (
                    "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ino")),
                    st_uid=os.geteuid()+100)
            return obj
        with patch.object(att.os, "fstat", side_effect=wrong_owner):
            result = att.run()
        self.assertEqual(result["observations"]["services/mpw_trx_guest_delivery.py"]["status"], "held")


if __name__ == "__main__":
    unittest.main()
