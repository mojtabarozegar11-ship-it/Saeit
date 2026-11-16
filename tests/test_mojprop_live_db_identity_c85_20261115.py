"""No-connection tests of the live database identity binding contract."""
import re
import unittest

from scripts.mojprop_live_database_identity_c85 import database_identity_digest


GOOD = {
    "ENGINE": "django.db.backends.mysql",
    "NAME": "mojplaywin_live",
    "HOST": "localhost",
    "PORT": "3306",
    "USER": "mojprop_app",
    "PASSWORD": "placeholder-must-never-enter-fingerprint",
}


class MojPropDbIdentityTests(unittest.TestCase):
    def test_id_is_64_lower_hex_and_stable(self):
        one = database_identity_digest(GOOD, "mojplaywin_live")
        two = database_identity_digest(dict(GOOD), "mojplaywin_live")
        self.assertEqual(one, two)
        self.assertRegex(one, r"^[a-f0-9]{64}$")

    def test_password_does_not_enter_digest(self):
        other = dict(GOOD, PASSWORD="new secret value")
        self.assertEqual(database_identity_digest(GOOD, "mojplaywin_live"),
                         database_identity_digest(other, "mojplaywin_live"))

    def test_connected_db_mismatch_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            database_identity_digest(GOOD, "some_other_live_database")

    def test_sqlite_and_postgres_fall_back_to_denial(self):
        for engine in ("django.db.backends.sqlite3", "django.db.backends.postgresql"):
            with self.subTest(engine=engine):
                with self.assertRaisesRegex(RuntimeError, "MariaDB"):
                    database_identity_digest(dict(GOOD, ENGINE=engine), GOOD["NAME"])

    def test_user_and_database_changes_change_id(self):
        baseline = database_identity_digest(GOOD, GOOD["NAME"])
        self.assertNotEqual(
            baseline, database_identity_digest(
                dict(GOOD, USER="another_user"), GOOD["NAME"]
            )
        )
        self.assertNotEqual(
            baseline, database_identity_digest(
                dict(GOOD, NAME="another_database"), "another_database"
            )
        )

    def test_malformed_or_unselected_database_fails(self):
        for name in ("", None, "other"):
            with self.subTest(name=name):
                with self.assertRaises(RuntimeError):
                    database_identity_digest(GOOD, name)

    def test_live_identity_source_only_queries_database(self):
        from pathlib import Path
        p = Path(__file__).resolve().parents[1] / "scripts/mojprop_live_database_identity_c85.py"
        text = p.read_text()
        self.assertIn('cursor.execute("SELECT DATABASE()")', text)
        for forbidden in ("DROP DATABASE", "CREATE DATABASE", "INSERT INTO", "UPDATE "):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
