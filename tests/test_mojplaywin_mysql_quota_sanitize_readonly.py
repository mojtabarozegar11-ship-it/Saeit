"""Synthetic data only: verify no MySQL database name or user leaks."""
import json
import unittest
from scripts.mojplaywin_mysql_quota_sanitize_readonly import sanitize


class MysqlQuotaSanitizeTests(unittest.TestCase):
    def test_mysql_names_not_logged(self):
        obj = {"result": {"status": 1, "data": [
            {"database": "SECRET_private_database", "disk_usage": 100000,
             "users": [{"user": "secret_owner"}]},
            {"database": "SECRET_other", "disk_usage": "2000"},
        ], "errors": None}}
        result = sanitize(obj, "mysql")
        self.assertEqual(result["database_count"], 2)
        self.assertEqual(result["reported_database_bytes_total"], 102000)
        self.assertTrue(result["all_sizes_reported"])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("owner", json.dumps(result))
        self.assertFalse(result["backup_created"])

    def test_failed_response_never_claims_success(self):
        obj = {"result": {"status": 0, "errors": ["secret credential error"]}}
        result = sanitize(obj, "quota")
        self.assertFalse(result["uapi_succeeded"])
        self.assertNotIn("credential", json.dumps(result))

    def test_quota_numeric_values_only(self):
        obj = {"result": {"status": 1, "data": {"bytes_used": 30000,
                                                 "byte_limit": 60000,
                                                 "path": "/private/home"}}}
        d = sanitize(obj, "quota")
        self.assertEqual(d["local_account_bytes_used"], 30000)
        self.assertNotIn("/private/", json.dumps(d))
        self.assertFalse(d["release_permitted"])


if __name__ == "__main__":
    unittest.main()
