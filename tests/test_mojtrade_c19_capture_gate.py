"""Offline CLI coverage checks; all fixtures are synthetic."""
from copy import deepcopy
from pathlib import Path
import hashlib
import importlib.util
import json
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "trading/mojtrade_ctrader_capture_gate.py"
spec = importlib.util.spec_from_file_location("mojtrade_ctrader_capture_gate", MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class CaptureGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        captures = {}
        for name in ("positions", "orders_history", "deals"):
            payload = json.dumps({"synthetic": name}).encode()
            (self.root / f"{name}.json").write_bytes(payload)
            captures[name] = {
                "file": f"{name}.json", "sha256": hashlib.sha256(payload).hexdigest(),
                "captured_utc": "2026-11-09T00:00:01Z", "count": 0,
            }
            if name != "positions":
                captures[name].update(from_utc_day="2026-11-08", to_utc_day="2026-11-08")
            if name == "orders_history":
                captures[name].update(available=0, returned=0)
        self.manifest = {"account": "123", "day": "2026-11-08",
                         "source": "ctrader-cli", "captures": captures}

    def result(self, manifest=None):
        return gate.check_capture(self.manifest if manifest is None else manifest, self.root)

    def test_complete_synthetic_manifest_is_never_authenticated(self):
        result = self.result()
        self.assertTrue(result["coverage_plausible"])
        self.assertFalse(result["broker_source_authenticated"])
        self.assertFalse(result["commercial_readiness"])

    def test_missing_source_fails_closed(self):
        del self.manifest["captures"]["deals"]
        with self.assertRaisesRegex(gate.CaptureError, "missing_cli_source"):
            self.result()

    def test_orders_history_available_greater_than_returned_is_blocked(self):
        self.manifest["captures"]["orders_history"].update(count=500, returned=500,
                                                            available=501)
        self.assertIn("orders_history_incomplete_or_inconsistent", self.result()["issues"])

    def test_deals_at_cap_is_ambiguous(self):
        self.manifest["captures"]["deals"]["count"] = 200
        self.assertIn("deals_at_ambiguous_cli_limit", self.result()["issues"])

    def test_truncated_day_scope_fails(self):
        self.manifest["captures"]["deals"]["from_utc_day"] = "2026-11-07"
        self.assertIn("incomplete_utc_day_scope:deals", self.result()["issues"])

    def test_early_capture_fails(self):
        self.manifest["captures"]["positions"]["captured_utc"] = "2026-11-08T23:59:59Z"
        self.assertIn("capture_before_utc_day_end:positions", self.result()["issues"])

    def test_hash_mismatch_fails(self):
        (self.root / "deals.json").write_text("tampered", encoding="utf-8")
        self.assertIn("hash_mismatch:deals", self.result()["issues"])

    def test_empty_capture_rejected(self):
        (self.root / "deals.json").write_bytes(b"")
        with self.assertRaisesRegex(gate.CaptureError, "empty_capture_file"):
            self.result()

    def test_outside_file_is_disallowed(self):
        self.manifest["captures"]["deals"]["file"] = "../outside.json"
        with self.assertRaisesRegex(gate.CaptureError, "unsafe_or_missing_file"):
            self.result()

    def test_bad_or_boolean_counts_fail(self):
        for value in (-1, True, "1"):
            with self.subTest(value=value):
                manifest = deepcopy(self.manifest)
                manifest["captures"]["deals"]["count"] = value
                with self.assertRaisesRegex(gate.CaptureError, "invalid_capture_count"):
                    self.result(manifest)

    def test_duplicate_json_manifest_key_is_rejected(self):
        with self.assertRaisesRegex(gate.CaptureError, "duplicate_manifest_key"):
            json.loads('{"account":"123","account":"999"}',
                       object_pairs_hook=gate._unique_object)


if __name__ == "__main__":
    unittest.main()
