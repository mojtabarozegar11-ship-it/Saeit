"""Offline acceptance tests for MojPlayWin Game Economy Stress Lab."""
import csv
from decimal import Decimal
import importlib.util
import io
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "factory_assets/staged_free_products/mpw-game-economy-stress-lab-v1"
spec = importlib.util.spec_from_file_location("mpw_economy_lab", PRODUCT / "economy_lab.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class EconomyLabTests(unittest.TestCase):
    def test_example_runs_twelve_sessions(self):
        result = lab.simulate(json.loads((PRODUCT / "example.json").read_text()))
        self.assertEqual(len(result["sessions"]), 12)
        self.assertGreater(Decimal(result["summary"]["cohort_earned"]), 0)

    def test_currency_conservation(self):
        row = lab.simulate({"sessions": 1, "initial_wallet": 100,
                            "earn_per_minute": 10, "spend_per_minute": 5,
                            "session_minutes": 10, "wallet_cap": 1000})["sessions"][0]
        self.assertEqual(row["wallet_after"], "150.0000")

    def test_spending_cannot_exceed_available(self):
        row = lab.simulate({"sessions": 1, "initial_wallet": 0,
                            "earn_per_minute": 1, "spend_per_minute": 9,
                            "session_minutes": 10})["sessions"][0]
        self.assertEqual(row["spent"], "10.0000")
        self.assertEqual(row["unmet_spending"], "80.0000")

    def test_wallet_cap(self):
        row = lab.simulate({"sessions": 1, "initial_wallet": 5,
                            "earn_per_minute": 10, "spend_per_minute": 1,
                            "session_minutes": 10, "wallet_cap": 20})["sessions"][0]
        self.assertEqual(row["wallet_overflow"], "75.0000")

    def test_retention(self):
        rows = lab.simulate({"sessions": 3, "players": 100,
                             "retention_per_session": 0.5})["sessions"]
        self.assertEqual([r["expected_active_players"] for r in rows],
                         ["100.0000", "50.0000", "25.0000"])

    def test_invalid_input(self):
        for value in (float("nan"), float("inf"), -1, None, True):
            with self.subTest(value=str(value)), self.assertRaises(ValueError):
                lab.simulate({"earn_per_minute": value})

    def test_bounded_sessions(self):
        with self.assertRaises(ValueError):
            lab.simulate({"sessions": 361})

    def test_csv_output(self):
        result = lab.simulate({"sessions": 2})
        rows = list(csv.DictReader(io.StringIO(lab.render_csv(result))))
        self.assertEqual(len(rows), 2)

    def test_release_is_explicitly_pending(self):
        self.assertIn("NOT listed in a live store", (PRODUCT / "README.md").read_text())
        self.assertIn("MIT License", (PRODUCT / "LICENSE").read_text())
