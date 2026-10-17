"""Safe cPanel inventory always remains non-deploying and redacts app roots."""
import unittest
from scripts.mojplaywin_cpanel_readonly_inventory import sanitize

class ReadonlyInventoryTests(unittest.TestCase):
    def test_main_shared_app_is_reported_without_leaking_root(self):
        info = sanitize({"result": {"status": 1, "data": [
            {"domain": "mojplaywin.com", "base_uri": "/", "app_root": "/home/example/Saeit-staging"},
            {"domain": "mojplaywin.com", "base_uri": "/picm/", "app_root": "/srv/picm"}
        ]}})
        self.assertEqual(len(info["mojplaywin_passenger_mappings"]), 2)
        self.assertTrue(info["mojplaywin_passenger_mappings"][0]["references_shared_saeit_staging"] or
                        info["mojplaywin_passenger_mappings"][1]["references_shared_saeit_staging"])
        self.assertIn("/picm/", info["known_independent_prefixes_with_explicit_passenger_mapping"])
        self.assertFalse(info["release_permitted"])
        self.assertNotIn("/home/example", str(info))

    def test_absent_uapi_mapping_is_not_proof_of_missing_child_site(self):
        info = sanitize({"result": {"status": 1, "data": []}})
        self.assertEqual(info["uapi_records_discovered"], 0)
        self.assertFalse(info["production_isolation_proven"])
        self.assertFalse(info["release_permitted"])

    def test_protected_other_domains_not_disclosed(self):
        info = sanitize({"result": {"status": 1, "data": [
            {"domain": "another-example.com", "base_uri": "/secret-project/", "app_root": "/private/path"},
        ]}})
        self.assertEqual(info["other_domain_mapping_count"], 1)
        self.assertNotIn("secret-project", str(info))
        self.assertNotIn("/private/path", str(info))

    def test_uapi_failure_is_not_accepted(self):
        with self.assertRaises(ValueError):
            sanitize({"result": {"status": 0, "errors": ["no access"]}})


if __name__ == "__main__":
    unittest.main()
