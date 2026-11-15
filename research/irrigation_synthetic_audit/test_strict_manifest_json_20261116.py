"""Regression checks: frozen R01 manifests must follow strict JSON syntax."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("verify_frozen_manifest.py")
spec = importlib.util.spec_from_file_location("r01_frozen_manifest", MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class StrictJsonManifestTests(unittest.TestCase):
    def check_raw(self, raw):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(raw, encoding="utf-8")
            return audit.verify(path)

    def test_nan_rejected(self):
        self.assertTrue(any("non-finite" in error for error in
                            self.check_raw('{"schema_version":1,"study":"R01","artifacts":NaN}')))

    def test_positive_infinity_rejected(self):
        self.assertTrue(any("non-finite" in error for error in
                            self.check_raw('{"schema_version":1,"study":"R01","artifacts":[Infinity]}')))

    def test_negative_infinity_rejected(self):
        self.assertTrue(any("non-finite" in error for error in
                            self.check_raw('{"schema_version":1,"study":"R01","artifacts":[-Infinity]}')))

    def test_standard_json_parses_before_artifact_validation(self):
        errors = self.check_raw(json.dumps({"schema_version": 1, "study": "R01", "artifacts": []}))
        self.assertTrue(any("artifact count" in error for error in errors))
        self.assertFalse(any("non-finite" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
