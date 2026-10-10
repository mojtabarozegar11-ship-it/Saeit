"""Unit tests for the staging DB preflight; all credentials are synthetic."""
import contextlib
import importlib.util
import io
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "staging_db_preflight.py"
spec = importlib.util.spec_from_file_location("staging_db_preflight", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class StagingDatabasePreflightTests(unittest.TestCase):
    def values(self, url="postgresql://stage_user:example%40pass@localhost:5432/saeit_stage"):
        return {
            "DATABASE_URL": url,
            "SAEIT_ENV": "staging",
            "DEBUG": "False",
            "STAGING_DB_IDENTITY": "saeit_stage",
            "PRODUCTION_DB_IDENTITY": "saeit_production",
        }

    def check(self, values):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = module.check(values)
        self.assertNotIn("example", output.getvalue())
        self.assertNotIn("stage_user", output.getvalue())
        return result, output.getvalue()

    def test_valid_isolated_postgresql_url(self):
        self.assertTrue(self.check(self.values())[0])

    def test_reject_sqlite(self):
        self.assertFalse(self.check(self.values("sqlite:///db.sqlite3"))[0])

    def test_reject_literal_at_in_password(self):
        result, output = self.check(self.values("postgresql://stage_user:example@pass@localhost/saeit_stage"))
        self.assertFalse(result)
        self.assertIn("CREDENTIAL_URL_ENCODING=FAIL", output)

    def test_reject_production_database_identity(self):
        v = self.values()
        v["PRODUCTION_DB_IDENTITY"] = "saeit_stage"
        self.assertFalse(self.check(v)[0])

    def test_reject_debug_true(self):
        v = self.values()
        v["DEBUG"] = "True"
        self.assertFalse(self.check(v)[0])

    def test_reject_nonstaging_environment(self):
        v = self.values()
        v["SAEIT_ENV"] = "production"
        self.assertFalse(self.check(v)[0])

if __name__ == "__main__":
    unittest.main()
