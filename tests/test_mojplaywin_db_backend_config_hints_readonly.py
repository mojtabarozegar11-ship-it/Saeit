"""Fixture-only redaction and fail-closed tests for DB config backend hints."""
import tempfile
import unittest
from pathlib import Path
from scripts.mojplaywin_db_backend_config_hints_readonly import category, inspect


class CandidateDatabaseHintsTests(unittest.TestCase):
    def test_secret_url_value_never_leaked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app = root / "app"
            web = root / "site"
            app.mkdir()
            web.mkdir()
            (app / ".env").write_text(
                "SECRET_KEY=never-print-123\nDATABASE_URL='postgres://superuser:ultrasecret@private-db.internal/database'\n"
            )
            data = inspect(app, web)
            self.assertEqual(data["candidate_backend_category"], "postgresql")
            self.assertFalse(data["effective_passenger_runtime_backend_confirmed"])
            self.assertFalse(data["full_database_backup_created"])
            self.assertFalse(data["release_permitted"])
            for secret in ("never-print", "ultrasecret", "private-db", "superuser", str(root)):
                self.assertNotIn(secret, str(data))

    def test_no_configuration_never_assumed_sqlite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "app").mkdir()
            (root / "web").mkdir()
            d = inspect(root / "app", root / "web")
            self.assertIsNone(d["candidate_backend_category"])
            self.assertFalse(d["actual_db_name_and_location_confirmed"])

    def test_ambiguous_conflicting_configs_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app = root / "app"
            web = root / "site"
            app.mkdir()
            web.mkdir()
            (app / ".env").write_text("DATABASE_URL=mysql://a:password@db/test\n")
            (web / ".env").write_text("DATABASE_URL=sqlite:////private/data.db\n")
            d = inspect(app, web)
            self.assertEqual(d["candidate_backend_category"], "ambiguous")
            self.assertFalse(d["release_permitted"])

    def test_unrelated_environment_values_are_ignored(self):
        self.assertIsNone(category("SECRET_KEY=hunter2\nPAYMENT_KEY=abc\n"))
        self.assertEqual(category("export DATABASE_URL=postgresql://x:y@host/db"), "postgresql")
        self.assertEqual(category("DATABASE_URL='not-a-url'"), "unrecognized")

if __name__ == "__main__":
    unittest.main()
