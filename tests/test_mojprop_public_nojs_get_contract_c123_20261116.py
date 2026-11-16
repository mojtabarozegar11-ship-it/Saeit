"""Offline contract regressions for live no-JS read-only evidence.

Tests create synthetic local GET response bodies only. No remote requests,
DB, purchases, emails, or submission of customer details.
"""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.mojprop_public_nojs_get_contract_c123 import (
    classify_document, read_and_classify, main,
)

INTAKE = b"""<!doctype html><html><body><form method="post" action="/moj-prop-intake/?format=html">
<input name="csrfmiddlewaretoken" value="SECRET_DO_NOT_LOG">
<input name="name"><input name="email"><select name="service"></select>
<select name="horizon"></select><textarea name="notes"></textarea>
<input name="idempotency_key"><input name="consent">
<button>Submit</button></form></body></html>"""

STATUS = b"""<!doctype html><html><body><form method="post" action="/moj-prop-status/?format=html">
<input name="csrfmiddlewaretoken" value="SECRET_DO_NOT_LOG">
<input name="receipt_token"></form></body></html>"""


class PublicNoJsContractTest(unittest.TestCase):
    def test_valid_intake_and_status_forms(self):
        self.assertTrue(classify_document(INTAKE, "intake"))
        self.assertTrue(classify_document(STATUS, "status"))

    def test_json_api_is_not_html(self):
        self.assertFalse(classify_document(
            b'{"ok":true,"csrf_token":"SECRET_DO_NOT_LOG","service":"moj-prop-intake"}',
            "intake",
        ))

    def test_404_error_page_not_a_buyer_form(self):
        self.assertFalse(classify_document(b"<html><body>404 Not Found</body></html>", "status"))

    def test_form_get_method_cannot_pass(self):
        self.assertFalse(classify_document(INTAKE.replace(b'method="post"', b'method="get"'), "intake"))

    def test_external_action_cannot_pass(self):
        self.assertFalse(classify_document(INTAKE.replace(
            b'/moj-prop-intake/?format=html', b'https://other.example/collect'
        ), "intake"))

    def test_missing_consent_and_csrf_fail(self):
        self.assertFalse(classify_document(INTAKE.replace(b'name="consent"', b'name="other"'), "intake"))
        self.assertFalse(classify_document(INTAKE.replace(b'name="csrfmiddlewaretoken"', b'name="other"'), "intake"))

    def test_receipt_lookup_never_uses_get(self):
        self.assertFalse(classify_document(STATUS.replace(b'method="post"', b'method="get"'), "status"))

    def test_duplicate_forms_fail(self):
        self.assertFalse(classify_document(INTAKE.replace(b"</body>", b"<form></form></body>"), "intake"))

    def test_scripts_fail_nojs(self):
        self.assertFalse(classify_document(STATUS.replace(b"</body>", b"<script>1</script></body>"), "status"))

    def test_oversized_body_fail_closed(self):
        self.assertFalse(classify_document(INTAKE + b" " * 300000, "intake"))

    def test_filesystem_missing_and_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = root / "intake.body"
            page.write_bytes(INTAKE)
            self.assertTrue(read_and_classify(page, "intake"))
            self.assertFalse(read_and_classify(root / "missing.body", "status"))
            alias = root / "alias.body"
            alias.symlink_to(page)
            self.assertFalse(read_and_classify(alias, "intake"))

    def test_cli_never_logs_csrf_or_receipt_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b = root / "a", root / "b"
            a.write_bytes(INTAKE)
            b.write_bytes(STATUS)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["probe.py", str(a), str(b)]), 0)
            text = output.getvalue()
            self.assertIn("PUBLIC_MOJPROP_NOJS_BACKEND_GATE=PASS", text)
            self.assertNotIn("SECRET_DO_NOT_LOG", text)
            b.write_text("not found")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["probe.py", str(a), str(b)]), 0)
            self.assertIn("PUBLIC_MOJPROP_NOJS_BACKEND_GATE=DEGRADED", output.getvalue())

    def test_unknown_kind_and_invalid_encoding_fail(self):
        self.assertFalse(classify_document(INTAKE, "billing"))
        self.assertFalse(classify_document(b"\xff\xfe", "intake"))


if __name__ == "__main__":
    unittest.main()
