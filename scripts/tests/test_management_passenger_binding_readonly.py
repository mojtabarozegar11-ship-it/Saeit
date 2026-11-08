"""Contract tests for redacted management Passenger evidence."""
import unittest

from scripts.management_passenger_binding_readonly import sanitize


class BindingReceiptTests(unittest.TestCase):
    def test_exact_source_root_is_visible_without_raw_path(self):
        result = sanitize({"result": {"status": 1, "data": [
            {"domain": "zomorodmelal.ir", "app_root": "/home/zomorod2/Saeit", "base_uri": "/", "python_version": "3.10"}
        ]}})
        self.assertTrue(result["exact_source_root_mapping_present"])
        self.assertEqual(result["target_domain_mappings"][0]["declared_python_version"], "3.10")
        self.assertNotIn("/home/zomorod2/Saeit", str(result))
        self.assertFalse(result["active_interpreter_attested"])
        self.assertFalse(result["release_permitted"])

    def test_relative_or_staging_paths_never_attest_exact_root(self):
        result = sanitize({"result": {"status": 1, "data": [
            {"domain": "zomorodmelal.ir", "app_root": "Saeit", "base_uri": "/"},
            {"domain": "www.zomorodmelal.ir", "app_root": "/home/zomorod2/Saeit-staging", "base_uri": "/private", "python_version": "unsafe secret"},
        ]}})
        self.assertFalse(result["exact_source_root_mapping_present"])
        self.assertEqual(result["target_domain_mappings"][0]["app_root_class"], "relative_saeit_unverified")
        self.assertEqual(result["target_domain_mappings"][1]["declared_python_version"], "not_declared")
        self.assertNotIn("/private", str(result))
        self.assertNotIn("unsafe secret", str(result))

    def test_no_target_mapping_is_not_an_attestation(self):
        result = sanitize({"result": {"data": [
            {"domain": "mojplaywin.com", "app_root": "/other", "base_uri": "/"}
        ]}})
        self.assertEqual(result["target_domain_mapping_count"], 0)
        self.assertFalse(result["exact_source_root_mapping_present"])
        self.assertFalse(result["release_permitted"])

    def test_uapi_uri_with_path_fallback_matches_existing_inventory_contract(self):
        result = sanitize({"result": {"data": [
            {"domain": "zomorodmelal.ir", "base_uri": "/", "path": "/home/zomorod2/Saeit"},
            {"domain": "mojplaywin.com", "base_uri": "/", "path": "/home/zomorod2/elsewhere"},
        ]}})
        self.assertEqual(result["uapi_records_discovered"], 2)
        self.assertEqual(result["target_domain_mapping_count"], 1)
        self.assertTrue(result["exact_source_root_mapping_present"])

    def test_explicit_uapi_failure_rejected(self):
        with self.assertRaises(ValueError):
            sanitize({"result": {"status": 0, "data": []}})


if __name__ == "__main__":
    unittest.main()
