"""Tests for the live PostgreSQL staging gate; never contact a real database."""
import importlib.util
import io
import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from contextlib import redirect_stdout

spec = importlib.util.spec_from_file_location("staging_postgres_live_gate", Path(__file__).resolve().parents[1] / "scripts" / "staging_postgres_live_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class LiveStagingGateTests(TestCase):
    def run_gate(self, environment):
        out = io.StringIO()
        with patch.dict(os.environ, environment, clear=True), redirect_stdout(out):
            code = gate.main()
        return code, out.getvalue()

    def test_refuses_production_before_django_import(self):
        code, out = self.run_gate({"SAEIT_ENV": "production", "DEBUG": "False"})
        self.assertEqual(code, 2)
        self.assertIn("STAGING_IDENTITY=FAIL", out)

    def test_refuses_debug_mode_before_django_import(self):
        code, out = self.run_gate({"SAEIT_ENV": "staging", "DEBUG": "True"})
        self.assertEqual(code, 2)
        self.assertIn("DEBUG_DISABLED=FAIL", out)

    def test_refuses_explicit_debug_setting(self):
        code, out = self.run_gate({"SAEIT_ENV": "staging", "DEBUG": "1"})
        self.assertEqual(code, 2)
        self.assertIn("DEBUG_DISABLED=FAIL", out)
