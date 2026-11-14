"""AST-extract and execute the exact Django view email adapter offline.

Only the function body is executed with a fake email validator. In the real
repository, this parses core/tron_gateway_web.py without requiring Django.
"""
import ast
from pathlib import Path
import unittest
from core.tron_gateway_identity import normalize_buyer_email


class DummyValidationError(Exception):
    pass


def dummy_validator(email):
    if not email.endswith("@example.com"):
        raise DummyValidationError("unrecognized domain")


def load_real_email_adapter():
    root = Path(__file__).resolve().parents[1]
    source = root / "core" / "tron_gateway_web.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name == "_valid_email"]
    if len(matches) != 1:
        raise AssertionError("Expected exactly one canonical buyer validator")
    function = matches[0]
    isolated = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    globals_map = {"normalize_buyer_email": normalize_buyer_email,
                   "validate_email": dummy_validator,
                   "ValidationError": DummyValidationError}
    exec(compile(isolated, str(source), "exec"), globals_map)
    return globals_map["_valid_email"]


class BuyerEmailAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = staticmethod(load_real_email_adapter())

    def test_canonical_email_accepted(self):
        self.assertEqual(self.adapter(" USER@EXAMPLE.COM "), "user@example.com")

    def test_leading_newline_rejected(self):
        with self.assertRaises(ValueError):
            self.adapter("\nuser@example.com")

    def test_trailing_carriage_return_rejected(self):
        with self.assertRaises(ValueError):
            self.adapter("user@example.com\r")

    def test_embedded_null_rejected(self):
        with self.assertRaises(ValueError):
            self.adapter("user@ex\0ample.com")

    def test_bidi_control_rejected(self):
        with self.assertRaises(ValueError):
            self.adapter("user@exam\u202eple.com")

    def test_django_validation_error_converts_to_value_error(self):
        with self.assertRaises(ValueError):
            self.adapter("user@invalid.test")

    def test_non_string_rejected(self):
        with self.assertRaises(ValueError):
            self.adapter(22)


if __name__ == "__main__":
    unittest.main()
