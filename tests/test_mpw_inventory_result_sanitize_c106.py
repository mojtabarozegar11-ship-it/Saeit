"""Fixed-envelope privacy and fail-closed tests using synthetic cPanel JSON."""
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import unittest

from scripts.mpw_private_checkout_live_source_inventory_20261116 import (
    EXPECTED, PREFIX,
)
from scripts import mpw_inventory_result_sanitize_c106 as target


def valid_doc():
    return {
        "schema": "mpw.cpanel.checkout.module-inventory.readonly.v1",
        "read_only": True,
        "customer_data_read": False,
        "application_modules_imported": False,
        "payment_or_invoice_created": False,
        "host_changed": False,
        "root_valid": True,
        "modules": {
            name: {
                "present": True,
                "regular": True,
                "parseable": True,
                "exports_present": True,
                "sha256": "e" * 64,
            } for name in EXPECTED
        },
    }


def payload(doc):
    return (PREFIX + json.dumps(doc, separators=(",", ":"))).encode("utf-8")


class ReadonlySanitizerTests(unittest.TestCase):
    def test_all_valid_fixture_reports_fixed_allowlist(self):
        result = target.sanitize(payload(valid_doc()))
        self.assertEqual(set(result["modules"]), set(EXPECTED))
        self.assertTrue(result["customer_sources_present"])
        self.assertTrue(result["customer_exports_present"])

    def test_declines_to_certify_sale_even_with_every_source_present(self):
        result = target.sanitize(payload(valid_doc()))
        self.assertIs(result["checkout_source_release_ready"], False)
        self.assertIs(result["payment_performed"], False)
        self.assertIs(result["data_modified"], False)

    def test_hashes_never_appear_in_sanitized_output(self):
        result = target.sanitize(payload(valid_doc()))
        self.assertNotIn("e" * 64, json.dumps(result))
        self.assertNotIn("sha256", json.dumps(result))

    def test_extra_remote_unknown_keys_are_not_echoed(self):
        doc = valid_doc()
        doc["SECRET_VALUE_NOT_FOR_PRINTING"] = "PRIVATE_STRING"
        doc["modules"][next(iter(EXPECTED))]["secret"] = "PRIVATE_STRING"
        text = json.dumps(target.sanitize(payload(doc)))
        self.assertNotIn("PRIVATE_STRING", text)

    def test_missing_customer_source_reports_false_without_error(self):
        doc = valid_doc()
        doc["modules"][next(iter(EXPECTED))]["present"] = False
        result = target.sanitize(payload(doc))
        self.assertFalse(result["customer_sources_present"])

    def test_customer_export_mismatch_reports_false(self):
        doc = valid_doc()
        doc["modules"][next(iter(EXPECTED))]["exports_present"] = False
        self.assertFalse(target.sanitize(payload(doc))["customer_exports_present"])

    def test_invalid_root_is_not_trusted(self):
        doc = valid_doc()
        doc["root_valid"] = False
        with self.assertRaises(ValueError):
            target.sanitize(payload(doc))

    def test_wrong_schema_is_denied(self):
        doc = valid_doc()
        doc["schema"] = "not-live-source-inventory"
        with self.assertRaises(ValueError):
            target.sanitize(payload(doc))

    def test_unexpected_module_path_is_denied(self):
        doc = valid_doc()
        doc["modules"]["/etc/shadow"] = {"present": True}
        with self.assertRaises(ValueError):
            target.sanitize(payload(doc))

    def test_missing_module_path_denied(self):
        doc = valid_doc()
        del doc["modules"][next(iter(EXPECTED))]
        with self.assertRaises(ValueError):
            target.sanitize(payload(doc))

    def test_untrusted_boolean_envelope_is_denied(self):
        for field, bad in (("read_only", "true"), ("customer_data_read", True),
                           ("host_changed", 0), ("payment_or_invoice_created", True),
                           ("application_modules_imported", True)):
            with self.subTest(field=field):
                doc = valid_doc()
                doc[field] = bad
                with self.assertRaises(ValueError):
                    target.sanitize(payload(doc))

    def test_nonboolean_file_status_is_denied(self):
        doc = valid_doc()
        doc["modules"][next(iter(EXPECTED))]["present"] = 1
        with self.assertRaises(ValueError):
            target.sanitize(payload(doc))

    def test_trailing_fake_log_line_denied(self):
        with self.assertRaises(ValueError):
            target.sanitize(payload(valid_doc()) + b"\nEXTRA")

    def test_invalid_utf8_denied(self):
        with self.assertRaises(UnicodeError):
            target.sanitize(b"\xff\xff")

    def test_empty_and_oversize_remote_payload_denied(self):
        for invalid in (b"", b"x" * (target.MAX_INPUT_BYTES + 1)):
            with self.subTest(length=len(invalid)), self.assertRaises(ValueError):
                target.sanitize(invalid)

    def test_real_module_cli_from_repo_root_executes_with_package_imports(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-B", "-m", "scripts.mpw_inventory_result_sanitize_c106"],
            input=payload(valid_doc()), cwd=root,
            capture_output=True, timeout=8, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertTrue(result.stdout.decode().startswith(target.REPORT_MARKER))
        self.assertNotIn("e" * 64, result.stdout.decode())

    def test_real_module_cli_rejects_invalid_input_without_traceback(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-B", "-m", "scripts.mpw_inventory_result_sanitize_c106"],
            input=b"untrusted", cwd=root,
            capture_output=True, timeout=8, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.decode().strip(),
                         "MPW_CPANEL_CHECKOUT_SOURCE_READONLY=INVALID_OR_INCOMPLETE")
        self.assertEqual(result.stderr, b"")

    def test_owner_live_workflow_uses_proven_module_invocation(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/mpw-cpanel-actual-checkout-source-inventory-c106.yml").read_text(encoding="utf-8")
        self.assertIn("python3 -B -m scripts.mpw_inventory_result_sanitize_c106", workflow)
        self.assertIn("author_association == 'OWNER'", workflow)

    def test_main_stdout_is_bounded_and_never_prints_private_sha(self):
        io = StringIO()
        stdin = type("FakeStdin", (), {"buffer": BytesIO(payload(valid_doc()))})()
        with patch.object(target.sys, "stdin", stdin), redirect_stdout(io):
            self.assertEqual(target.main(), 0)
        printed = io.getvalue()
        self.assertTrue(printed.startswith(target.REPORT_MARKER))
        self.assertNotIn("e" * 64, printed)

    def test_main_fails_closed_on_invalid_source_bytes(self):
        io = StringIO()
        stdin = type("FakeStdin", (), {"buffer": BytesIO(b"bad")})()
        with patch.object(target.sys, "stdin", stdin), redirect_stdout(io):
            self.assertEqual(target.main(), 2)
        self.assertEqual(io.getvalue().strip(),
                         "MPW_CPANEL_CHECKOUT_SOURCE_READONLY=INVALID_OR_INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
