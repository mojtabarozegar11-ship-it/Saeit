"""Offline invention regression checks; no broker or live trading."""

import importlib.util
import json
import math
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "mojtrade_strategy_foundry.py"
SOURCE = REPO_SOURCE if REPO_SOURCE.is_file() else Path(__file__).with_name("mojtrade_strategy_foundry.py")
spec = importlib.util.spec_from_file_location("mojtrade_strategy_foundry", SOURCE)
foundry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(foundry)


def market_data(count=300):
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows = []
    prev = 100.0
    for i in range(count):
        close = 100 + 0.04 * i + 3.2 * math.sin(i / 4.0) + 2.2 * math.sin(i / 15.0)
        open_price = prev
        gap = abs(close - open_price) + .14
        stamp = start + timedelta(minutes=i)
        rows.append({
            "t": stamp.isoformat(), "available_at": stamp.isoformat(),
            "open": open_price, "high": max(open_price, close) + gap * .1,
            "low": min(open_price, close) - gap * .1, "close": close,
            "spread_bps": 3.0,
        })
        prev = close
    return {"source_id": "synthetic-fixture-not-real-market", "symbol": "BTC/USD",
            "interval_seconds": 60, "bars": rows}


class StrategyFoundryTests(unittest.TestCase):
    def test_reproducible_invention_with_three_structurally_distinct_births(self):
        data = market_data()
        first = foundry.invent(data, seed=173, max_trials=64)
        second = foundry.invent(data, seed=173, max_trials=64)
        self.assertEqual(first, second)
        births = first["birth_certificates"]
        self.assertGreaterEqual(len(births), 3)
        self.assertEqual(len({b["structure_signature"] for b in births}), len(births))
        self.assertTrue(all(b["receipt_sha256"] ==
                            foundry.digest({k: v for k, v in b.items() if k != "receipt_sha256"})
                            for b in births))
        self.assertEqual(first["orders"], 0)
        self.assertEqual(first["execution"], "disabled")
        self.assertFalse(any(b["broker_eligible"] for b in births))
        self.assertEqual(len(first["trial_ledger"]), 64)
        self.assertEqual(first["report_sha256"], foundry.digest(
            {k: v for k, v in first.items() if k != "report_sha256"}))
        self.assertGreater(first["training_discovery"]["primitive_hypotheses_tested"], 0)
        self.assertTrue(all(b["discovery_mode"] == "training-only-conditional-event-synthesis"
                            for b in births))

    def test_parameter_tuning_does_not_count_as_structural_invention(self):
        a = {"operator": "ALL", "side": "BUY", "hold_bars": 3, "stop_atr": 2.0,
             "conditions": [
                 {"feature": "momentum", "window": 6, "comparison": "GT", "threshold": .1},
                 {"feature": "range_location", "window": 12, "comparison": "LT", "threshold": -.1},
             ]}
        b = json.loads(json.dumps(a))
        b["conditions"][0]["window"] = 24
        b["conditions"][0]["threshold"] = .3
        b["stop_atr"] = 2.5
        self.assertEqual(foundry.structure_signature(a), foundry.structure_signature(b))
        b["conditions"][0]["feature"] = "volatility_shift"
        self.assertNotEqual(foundry.structure_signature(a), foundry.structure_signature(b))

    def test_no_future_candle_in_signal(self):
        data = foundry.validate_dataset(market_data())
        bars = data["bars"]
        program = {"operator": "ANY", "side": "SELL", "hold_bars": 3, "stop_atr": 2.0,
                   "conditions": [
                       {"feature": "momentum", "window": 6, "comparison": "GT", "threshold": .1},
                       {"feature": "mean_deviation", "window": 12, "comparison": "LT", "threshold": -.5},
                   ]}
        before = foundry.signal(program, bars, 110)
        altered = json.loads(json.dumps(bars))
        for i in range(111, len(altered)):
            altered[i]["close"] = 999999
        self.assertEqual(before, foundry.signal(program, altered, 110))

    def test_discovery_never_reads_holdout_bars(self):
        bars = foundry.validate_dataset(market_data())["bars"]
        split = int(.65 * len(bars))
        original = foundry.discover_training_hypotheses(bars, split)
        changed = json.loads(json.dumps(bars))
        for row in changed[split:]:
            row["close"] = 999999
        self.assertEqual(original, foundry.discover_training_hypotheses(changed, split))

    def test_sequence_order_is_distinct_but_commutative_all_is_not(self):
        conditions = [
            {"feature": "momentum", "window": 6, "comparison": "GT", "threshold": .1},
            {"feature": "range_location", "window": 12, "comparison": "LT", "threshold": -.1},
        ]
        program = {"operator": "SEQUENCE", "side": "BUY", "hold_bars": 3,
                   "stop_atr": 1.5, "conditions": conditions}
        reversed_program = json.loads(json.dumps(program))
        reversed_program["conditions"].reverse()
        self.assertNotEqual(foundry.structure_signature(program),
                            foundry.structure_signature(reversed_program))
        program["operator"] = "ALL"
        reversed_program["operator"] = "ALL"
        self.assertEqual(foundry.structure_signature(program),
                         foundry.structure_signature(reversed_program))

    def test_flat_market_has_no_invented_positive_training_hypotheses(self):
        data = market_data()
        for row in data["bars"]:
            row.update({"open": 100.0, "high": 100.01, "low": 99.99, "close": 100.0})
        with self.assertRaisesRegex(foundry.FoundryError, "no_valid_training_hypotheses"):
            foundry.invent(data, max_trials=12)

    def test_closed_bar_approximation_never_fills_at_unavailable_open(self):
        bars = foundry.validate_dataset(market_data())["bars"]
        p = {"operator": "ANY", "side": "BUY", "hold_bars": 3, "stop_atr": 1.5,
             "conditions": [
                 {"feature": "momentum", "window": 6, "comparison": "GT", "threshold": .1},
                 {"feature": "range_location", "window": 6, "comparison": "GT", "threshold": .1},
             ]}
        result = foundry._evaluate(p, bars, 0, 190)
        self.assertGreater(len(result["outcomes"]), 0)
        self.assertTrue(all(x["entry_index"] > x["decision_index"]
                            and x["exit_index"] > x["entry_index"]
                            and x["exit_index"] < 190 for x in result["outcomes"]))

    def test_higher_cost_not_a_free_profit(self):
        bars = foundry.validate_dataset(market_data())["bars"]
        p = {"operator": "ANY", "side": "BUY", "hold_bars": 3, "stop_atr": 1.5,
             "conditions": [
                 {"feature": "momentum", "window": 6, "comparison": "GT", "threshold": .1},
                 {"feature": "range_location", "window": 6, "comparison": "GT", "threshold": .1},
             ]}
        cheap = foundry._evaluate(p, bars, 0, 190, cost_bps=1)
        dear = foundry._evaluate(p, bars, 0, 190, cost_bps=40)
        self.assertEqual(cheap["trades"], dear["trades"])
        self.assertLess(dear["net_total_return_additive"], cheap["net_total_return_additive"])

    def test_reject_future_unavailable_bad_data_and_injected_operator(self):
        for variation in ("gap", "future", "nan", "bad_spread", "duplicate"):
            data = market_data()
            if variation == "gap":
                data["bars"][50]["t"] = data["bars"][49]["t"]
            if variation == "future":
                data["bars"][50]["available_at"] = (
                    datetime.fromisoformat(data["bars"][50]["t"]) +
                    timedelta(minutes=2)).isoformat()
            if variation == "nan":
                data["bars"][50]["close"] = float("nan")
            if variation == "bad_spread":
                data["bars"][50]["spread_bps"] = -1
            if variation == "duplicate":
                data["bars"][50] = data["bars"][49].copy()
            with self.subTest(variation=variation), self.assertRaises(foundry.FoundryError):
                foundry.validate_dataset(data)
        with self.assertRaises(foundry.FoundryError):
            foundry.validate_program({"operator": "EXEC", "side": "BUY", "hold_bars": 1,
                                      "stop_atr": 2.0, "conditions": [{"feature": "__import__"}]})
        with self.assertRaises(foundry.FoundryError):
            foundry.invent(market_data(), max_trials=1000000)

    def test_private_output_permissions_and_no_partial_replace(self):
        result = foundry.invent(market_data(), seed=9, max_trials=12)
        with tempfile.TemporaryDirectory() as td:
            private = Path(td) / "private"
            private.mkdir(mode=0o700)
            output = private / "research.json"
            foundry.write_private(result, output)
            self.assertEqual(json.loads(output.read_text()), result)
            self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
            self.assertEqual(sorted(p.name for p in private.iterdir()), ["research.json"])
            os.chmod(private, 0o755)
            with self.assertRaises(foundry.FoundryError):
                foundry.write_private(result, output)
            self.assertEqual(json.loads(output.read_text()), result)

    def test_no_orders_or_untrusted_code_execution_interfaces(self):
        names = dir(foundry)
        self.assertFalse(any("broker" in name.lower() or "order" in name.lower()
                             for name in names if not name.startswith("_")))
        result = foundry.invent(market_data(), seed=10, max_trials=10)
        self.assertEqual(result["public_signals"], 0)
        self.assertEqual(result["mode"], "RESEARCH_ONLY")


if __name__ == "__main__":
    unittest.main()
