"""CLI contract tests; use temporary local inputs and no network."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from farm_economics_cli import main
from farm_economics_validator import FIELDS


class CliTests(unittest.TestCase):
    def test_valid_csv_outputs_machine_readable_json(self):
        row = ["farm01", "wheat", "2026-01-01", "2026-06-30", "USD", "kg",
               "80", "80", "800", "20", "300", "200", "50"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            path.write_text(",".join(FIELDS) + "\n" + ",".join(row) + "\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main([str(path)])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["records"][0]["economic_profit"], "270")

    def test_bad_input_does_not_emit_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text("bad,header\n1,2\n", encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main([str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("Input rejected:", err.getvalue())


if __name__ == "__main__":
    unittest.main()
