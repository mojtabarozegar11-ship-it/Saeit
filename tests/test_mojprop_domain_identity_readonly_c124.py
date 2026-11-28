import unittest

from scripts.mojprop_domain_identity_readonly_c124 import (
    DOMAIN, _classify_uapi_error, _domain_in, _find_path, _safe_home_path,
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


    def test_uapi_error_classifier_returns_only_safe_categories(self):
        cases = (
            (b"Permission denied for API call", "permission_denied"),
            (b"Unknown module DomainInfo", "uapi_module_not_found"),
            (b"Unknown function list_domains", "uapi_function_not_found"),
            (b"API access disabled", "uapi_access_disabled"),
            (b"Internal server error: private detail", "cpanel_runtime_error"),
            (b"unrecognized option --bad", "cli_option_rejected"),
            (b"opaque provider message with account data", "unclassified_nonzero_exit"),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                actual = _classify_uapi_error(raw)
                self.assertEqual(actual, expected)
                self.assertNotIn(raw.decode(), actual)

    def test_uapi_io_diagnostics_are_metadata_only(self):
        from scripts import mojprop_domain_identity_readonly_c124 as module
        module._LAST_UAPI_IO.clear()
        module._LAST_UAPI_IO.update({
            "exit_code": 1,
            "stdout_bytes": 0,
            "stderr_bytes": 42,
            "stderr_empty": False,
            "stdout_empty": True,
        })
        self.assertEqual(module._LAST_UAPI_IO["exit_code"], 1)
        self.assertEqual(module._LAST_UAPI_IO["stderr_bytes"], 42)
        self.assertNotIn("stderr", module._LAST_UAPI_IO.keys() - {"stderr_bytes", "stderr_empty"})

    def test_target_domain_constant_is_exact(self):
        self.assertEqual(DOMAIN, "mojprop.top")


if __name__ == "__main__":
    unittest.main()
