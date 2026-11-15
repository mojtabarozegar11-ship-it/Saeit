"""Regression: guest identity conflict must be a real raise, not inert text."""
import ast
import unittest

from scripts.mpw_email_required_preflight_20261114 import _has_raise_string

MESSAGE = "Guest buyer email identity conflict"


class IdentityConflictRaiseEvidence(unittest.TestCase):
    def check(self, source):
        return _has_raise_string(ast.parse(source), MESSAGE)

    def test_real_raise(self):
        self.assertTrue(self.check('def f():\n    raise ValueError("Guest buyer email identity conflict")\n'))

    def test_inert_assignment_is_not_denial(self):
        self.assertFalse(self.check('def f():\n    message = "Guest buyer email identity conflict"\n'))

    def test_inert_expression_is_not_denial(self):
        self.assertFalse(self.check('def f():\n    "Guest buyer email identity conflict"\n'))

    def test_unrelated_raise_is_not_denial(self):
        self.assertFalse(self.check('def f():\n    message = "Guest buyer email identity conflict"\n    raise ValueError("other")\n'))

    def test_missing_exception_is_not_denial(self):
        self.assertFalse(self.check('def f():\n    message = "Guest buyer email identity conflict"\n    raise\n'))


    def test_disabled_if_false_raise_is_not_denial(self):
        self.assertFalse(self.check('def f():\\n    if False:\\n        raise ValueError("Guest buyer email identity conflict")\\n'))

    def test_disabled_if_zero_raise_is_not_denial(self):
        self.assertFalse(self.check('def f():\\n    if 0:\\n        raise ValueError("Guest buyer email identity conflict")\\n'))

    def test_live_else_branch_is_denial(self):
        self.assertTrue(self.check('def f():\\n    if False:\\n        pass\\n    else:\\n        raise ValueError("Guest buyer email identity conflict")\\n'))

    def test_disabled_else_branch_is_not_denial(self):
        self.assertFalse(self.check('def f():\\n    if True:\\n        pass\\n    else:\\n        raise ValueError("Guest buyer email identity conflict")\\n'))


if __name__ == "__main__":
    unittest.main()
