"""No-network, no-DB regressions for the Passenger TRX release dependency gate."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.mpw_trx_checkout_dependency_release_gate import (
    PINNED_SHA256,
    audit,
)


SOURCE = {
    "mojplaywin_native_chain_verify.py":
        b"def tron_address_to_hex(address):\n    return address\n"
        b"def verify_trx_transfer(tx):\n    return bool(tx)\n",
    "mojplaywin_direct_wallet_invoice.py":
        b"class SpotRate:\n    pass\n",
    "mojplaywin_direct_wallet_rates.py":
        b"class RateFeedUnavailable(Exception):\n    pass\n"
        b"def fetch_fresh_rates():\n    return {}\n",
}


class NativeTrxReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.app = root / "candidate"
        self.scripts = self.app / "scripts"
        self.scripts.mkdir(parents=True)
        self.wsgi = root / "passenger_wsgi.py"
        self.wsgi.write_text("APP='" + str(self.app) + "'\n", encoding="utf-8")
        self.expected = {}
        for name, content in SOURCE.items():
            (self.scripts / name).write_bytes(content)
            self.expected[name] = hashlib.sha256(content).hexdigest()

    def check(self):
        return audit(self.app, self.wsgi, pinned_hashes=self.expected)

    def test_exact_complete_bundle_passes(self):
        result = self.check()
        self.assertTrue(result["ready"])
        self.assertEqual(result["expected_modules"], 3)
        self.assertEqual(len(result["checked_source_hashes"]), 3)

    def test_prod_pinned_real_hashes_are_immutable(self):
        self.assertEqual(
            PINNED_SHA256["mojplaywin_direct_wallet_rates.py"],
            "290eae3ed4669a8bb4b98fdcaafca469b37d19bc8a49acded133db46f467264c",
        )
        self.assertEqual(len(PINNED_SHA256), 3)

    def test_missing_module_fails_closed(self):
        for name in self.expected:
            with self.subTest(module=name):
                path = self.scripts / name
                saved = path.read_bytes()
                path.unlink()
                result = self.check()
                self.assertFalse(result["ready"])
                self.assertIn("missing_or_symlink:" + name, result["error_codes"])
                path.write_bytes(saved)

    def test_replaced_or_incomplete_module_fails_closed(self):
        name = "mojplaywin_direct_wallet_rates.py"
        path = self.scripts / name
        path.write_bytes(b"malicious or outdated code\n")
        result = self.check()
        self.assertFalse(result["ready"])
        self.assertIn("sha256_mismatch:" + name, result["error_codes"])

    def test_broken_wsgirouting_fails_even_when_modules_match(self):
        self.wsgi.write_text("APP='/other/application'\n", encoding="utf-8")
        result = self.check()
        self.assertFalse(result["ready"])
        self.assertIn("wsgi_effective_app_root_drift", result["error_codes"])

    def test_duplicate_wsgi_assignment_with_comment_fails_closed(self):
        self.wsgi.write_text(
            "APP='" + str(self.app) + "'\n"
            "APP='/other/application'  # Passenger override\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertFalse(result["ready"])
        self.assertIn("wsgi_effective_app_root_drift", result["error_codes"])

    def test_computed_wsgi_assignment_fails_closed(self):
        self.wsgi.write_text(
            "ROOT='" + str(self.app) + "'\nAPP=ROOT\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertFalse(result["ready"])
        self.assertIn("wsgi_effective_app_root_drift", result["error_codes"])

    def test_assignment_looking_text_is_not_accepted_as_wsgi_config(self):
        self.wsgi.write_text(
            "message = \'APP=\\\"" + str(self.app) + "\\\"\'\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertFalse(result["ready"])
        self.assertIn("wsgi_effective_app_root_drift", result["error_codes"])

    def test_python_source_symlink_is_not_accepted(self):
        name = "mojplaywin_native_chain_verify.py"
        path = self.scripts / name
        copy = self.app / "copy.py"
        path.rename(copy)
        try:
            path.symlink_to(copy)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        result = self.check()
        self.assertIn("missing_or_symlink:" + name, result["error_codes"])

    def test_missing_required_function_not_accepted_even_with_matching_hash(self):
        name = "mojplaywin_native_chain_verify.py"
        body = b"def unrelated_function():\n    pass\n"
        (self.scripts / name).write_bytes(body)
        expected = dict(self.expected)
        expected[name] = hashlib.sha256(body).hexdigest()
        result = audit(self.app, self.wsgi, pinned_hashes=expected)
        self.assertIn("api_contract_missing:" + name, result["error_codes"])

    def test_preflight_does_not_modify_app_files(self):
        before = {path.name: path.read_bytes() for path in self.scripts.iterdir()}
        self.check()
        after = {path.name: path.read_bytes() for path in self.scripts.iterdir()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
