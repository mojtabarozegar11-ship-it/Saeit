"""Offline fixtures only; prove read-only preflight never implies recovery."""
import tempfile
import unittest
from pathlib import Path

from scripts.mojplaywin_backup_restore_readiness_readonly import (
    inspect, scan_media, file_stat,
)


class BackupRestoreReadonlyTests(unittest.TestCase):
    def test_sqlite_candidate_is_not_authoritative_and_cannot_approve_release(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app = root / "app"
            site = root / "www"
            app.mkdir()
            site.mkdir()
            (app / "db.sqlite3").write_bytes(b"fake-db")
            media = app / "media"
            media.mkdir()
            (media / "private-filename.txt").write_bytes(b"not-private-proof")
            report = inspect(root, app, site)
            self.assertTrue(report["sqlite_candidate"]["exists_regular"])
            self.assertTrue(report["candidate_media_roots"]["shared_django_media"]["complete"])
            self.assertEqual(report["candidate_media_roots"]["shared_django_media"]["sample_file_count"], 1)
            for forbidden in ("private-filename", "fake-db", str(root)):
                self.assertNotIn(forbidden, str(report))
            for required_false in (
                "database_engine_live_confirmed",
                "complete_production_backup_created",
                "isolated_restore_rehearsal_passed",
                "protected_subsite_backup_coverage_verified",
                "release_permitted",
            ):
                self.assertFalse(report[required_false])

    def test_symlink_media_root_is_not_followed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outside = root / "other"
            outside.mkdir()
            (outside / "hidden.txt").write_text("secret")
            fake = root / "media"
            fake.symlink_to(outside, target_is_directory=True)
            r = scan_media(fake)
            self.assertFalse(r["directory_exists"])
            self.assertEqual(r["sample_file_count"], 0)

    def test_incomplete_media_scan_not_misreported_as_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a").write_text("1")
            (root / "b").write_text("2")
            r = scan_media(root, limit=1)
            self.assertFalse(r["complete"])

    def test_missing_paths_are_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            r = inspect(root / "missing", root / "app", root / "www")
            self.assertFalse(r["hosting_account_disk"]["measured"])
            self.assertFalse(r["sqlite_candidate"]["exists_regular"])
            self.assertFalse(r["all_db_and_media_locations_found"])
            self.assertFalse(r["release_permitted"])

    def test_symlink_sqlite_not_read(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "db"
            target.write_bytes(b"private")
            path = root / "db.sqlite3"
            path.symlink_to(target)
            self.assertFalse(file_stat(path)["exists_regular"])


if __name__ == "__main__":
    unittest.main()
