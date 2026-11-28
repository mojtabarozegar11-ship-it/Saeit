import unittest

from scripts.mojprop_domain_identity_readonly_c124 import (
    DOMAIN, _domain_in, _find_path, _safe_home_path,
)


class C124DomainIdentityTests(unittest.TestCase):
    def test_exact_domain_matching_is_case_insensitive(self):
        self.assertTrue(_domain_in({"addon_domains": ["MOJPROP.TOP"]}))
        self.assertFalse(_domain_in({"addon_domains": ["mojplaywin.com"]}))

    def test_only_owner_home_paths_are_returned(self):
        self.assertEqual(
            _safe_home_path("/home/zomorod2/mojprop.top"),
            "/home/zomorod2/mojprop.top",
        )
        self.assertIsNone(_safe_home_path("/home/zomorod2/../other"))
        self.assertIsNone(_safe_home_path("/home/other/mojprop.top"))
        self.assertIsNone(_safe_home_path("/etc/passwd"))

    def test_docroot_is_extracted_from_allowlisted_keys_only(self):
        self.assertEqual(
            _find_path({"documentroot": "/home/zomorod2/mojprop.top"},
                       {"documentroot", "docroot"}),
            "/home/zomorod2/mojprop.top",
        )
        self.assertIsNone(
            _find_path({"secret": "/home/zomorod2/private"},
                       {"documentroot", "docroot"}),
        )

    def test_target_domain_constant_is_exact(self):
        self.assertEqual(DOMAIN, "mojprop.top")


if __name__ == "__main__":
    unittest.main()
