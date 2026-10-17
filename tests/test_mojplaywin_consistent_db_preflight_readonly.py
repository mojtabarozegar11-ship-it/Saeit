import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.mojplaywin_consistent_db_preflight_readonly import source_url, inspect


class ConsistentBackupPreflightTests(unittest.TestCase):
    def test_parses_mysql_uri_locally_never_prints_secrets(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/".env"
            p.write_text("DATABASE_URL=mysql://test_user:DO_NOT_LEAK@localhost/account_db\nSECRET_KEY=PRIVATE\n")
            parsed=source_url([p])
            self.assertEqual(parsed.scheme, "mysql")
            self.assertNotIn("DO_NOT_LEAK", str(inspect([Path(td)/"missing"])))
            self.assertNotIn("account_db", str(inspect([Path(td)/"missing"])))

    def test_conflicting_db_urls_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/".env"
            q=Path(td)/".env.production"
            p.write_text("DATABASE_URL=mysql://x:p@localhost/db\n")
            q.write_text("DATABASE_URL=mysql://x:p@localhost/db2\n")
            self.assertIsNone(source_url([p,q]))

    def test_other_db_engine_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/".env"
            p.write_text("DATABASE_URL=postgresql://x:p@localhost/db\n")
            self.assertIsNone(source_url([p]))

    def test_no_connect_on_no_valid_url(self):
        with patch("scripts.mojplaywin_consistent_db_preflight_readonly.verify_connection") as client, \
             patch("scripts.mojplaywin_consistent_db_preflight_readonly.path_size",return_value={"exists":False,"bytes":None,"measurement_complete":False}):
            r = inspect(paths=[])
            client.assert_not_called()
            self.assertFalse(r["backup_created"])
            self.assertFalse(r["release_permitted"])
            self.assertFalse(r["cPanel_account_has_same_single_database_and_connection_works"])


if __name__ == "__main__":
    unittest.main()
