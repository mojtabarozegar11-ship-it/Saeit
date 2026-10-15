"""Isolated market/readiness policy regressions: never authorizes retail sale."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "astra_market_readiness_gate.py"
PILOT = ROOT / "research" / "astra-water-margin-us-primary-market-pilot.json"
spec = importlib.util.spec_from_file_location("astra_market_gate_test", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class MarketGateTests(unittest.TestCase):
    def packet(self):
        return json.loads(PILOT.read_text(encoding="utf-8"))

    def test_real_pilot_remains_unpriced_unqualified(self):
        p = gate.assess(self.packet())
        self.assertEqual(p["sources_listed"], 9)
        self.assertEqual(p["competitors_listed"], 4)
        self.assertGreaterEqual(p["distinct_competitor_publishers"], 2)
        self.assertGreaterEqual(p["compared_feature_dimensions"], 4)
        self.assertEqual(p["sources_independently_attested"], 0)
        self.assertEqual(p["real_buyer_interviews_attested"], 0)
        self.assertIsNone(p["professional_quality_score"])
        self.assertFalse(p["buyer_willingness_to_pay_verified"])
        self.assertFalse(p["sale_price_verified"])
        self.assertFalse(p["build_authorized"])
        self.assertFalse(p["publish_authorized"])
        self.assertFalse(p["payment_authorized"])
        self.assertIn("COLLECT_AND_INDEPENDENTLY_CHECK_100_PRODUCT_EVIDENCE_ITEMS",
                      p["next_research_actions"])

    def test_one_hundred_url_only_records_never_prove_buyer_intent(self):
        p = self.packet()
        for i in range(10, 101):
            p["sources"].append({
                "id": "E" + str(i).zfill(2),
                "url": "https://example.org/unverified/" + str(i),
                "role": "context",
                "claim": "problem_context",
            })
        result = gate.assess(p)
        self.assertEqual(result["sources_listed"], 100)
        self.assertEqual(result["sources_independently_attested"], 0)
        self.assertEqual(result["real_buyer_interviews_attested"], 0)
        self.assertFalse(result["publish_authorized"])
        self.assertFalse(result["payment_authorized"])
        self.assertIn("VERIFY_WILLINGNESS_TO_PAY_WITH_REAL_BUYERS",
                      result["next_research_actions"])

    def test_operator_cannot_self_authorize_price_or_sale(self):
        for injection in (
            {"publish_authorized": True},
            {"sale_price_verified": True},
            {"buyer_willingness_to_pay_verified": True},
            {"quality_score": 100},
        ):
            with self.subTest(injection=injection):
                p = self.packet()
                p.update(injection)
                with self.assertRaisesRegex(ValueError, "exact five-field"):
                    gate.assess(p)

    def test_duplicate_urls_and_ids_rejected(self):
        p = self.packet()
        p["sources"].append(copy.deepcopy(p["sources"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            gate.assess(p)
        p = self.packet()
        p["sources"][-1]["url"] = p["sources"][0]["url"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            gate.assess(p)

    def test_ip_private_or_insecure_reference_rejected(self):
        for url in (
            "http://example.com/a",
            "https://127.0.0.1/a",
            "https://localhost/a",
            "https://host.internal/a",
            "https://user:password@example.com/a",
            "https://example.com:8443/a",
            "https://example.com/a#fragment",
        ):
            with self.subTest(url=url):
                p = self.packet()
                p["sources"][0]["url"] = url
                with self.assertRaisesRegex(ValueError, "source URL"):
                    gate.assess(p)

    def test_unknown_or_claimed_absent_competitor_features_rejected(self):
        for state in ("absent", "documented_absent", True, 1):
            with self.subTest(state=state):
                p = self.packet()
                p["competitors"][0]["features"]["offline_access"] = state
                with self.assertRaisesRegex(ValueError, "feature"):
                    gate.assess(p)

    def test_competitor_cannot_reference_context_source(self):
        p = self.packet()
        p["competitors"][0]["source_ids"] = ["E01"]
        with self.assertRaisesRegex(ValueError, "direct source"):
            gate.assess(p)

    def test_malformed_or_misclassified_source_denied(self):
        p = self.packet()
        p["sources"][0]["claim"] = "willingness_to_pay"
        with self.assertRaisesRegex(ValueError, "classification"):
            gate.assess(p)
        p = self.packet()
        p["sources"][0]["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "metadata"):
            gate.assess(p)

    def test_synthetic_cli_private_output_and_zero_mutations(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            original = PILOT.read_bytes()
            result_path = root / "market-private-review.json"
            p = subprocess.run([
                sys.executable, str(SCRIPT), "--input", str(PILOT),
                "--output", str(result_path),
            ], capture_output=True, text=True, timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("ASTRA_MARKET_RELEASE_AUTHORIZED=false", p.stdout)
            report = json.loads(result_path.read_text())
            self.assertEqual(report["factory_mutations"], 0)
            self.assertEqual(report["network_requests"], 0)
            self.assertFalse(report["build_authorized"])
            self.assertEqual(result_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(PILOT.read_bytes(), original)
            overwrite = subprocess.run([
                sys.executable, str(SCRIPT), "--input", str(PILOT),
                "--output", str(PILOT),
            ], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(overwrite.returncode, 0)


if __name__ == "__main__":
    unittest.main()
