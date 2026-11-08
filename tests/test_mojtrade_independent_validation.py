"""Unseen-data, multiplicity and private one-shot verification regressions."""

import copy
import importlib.util
import json
import math
import stat
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts" / "mojtrade_independent_validation.py"
FIX = ROOT / "tests" / "test_mojtrade_strategy_foundry.py"
if not SRC.is_file():
    SRC = Path(__file__).with_name("mojtrade_independent_validation.py")
    FIX = Path(__file__).with_name("test_mojtrade_strategy_foundry.py")
sys.path.insert(0, str(SRC.parent))
spec = importlib.util.spec_from_file_location("mojtrade_independent_validation", SRC)
oos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oos)
fspec = importlib.util.spec_from_file_location("oos_market_fixture", FIX)
fixture = importlib.util.module_from_spec(fspec)
fspec.loader.exec_module(fixture)


def unseen_period(training, days=14):
    unseen = copy.deepcopy(training)
    unseen["source_id"] = "synthetic-unseen-not-provider-verified"
    previous = 130.0
    for i, bar in enumerate(unseen["bars"]):
        close = 130 + .025 * i + 4.1 * math.sin((i + 23) / 5.4) + 2.5 * math.sin(i / 17 + 1)
        gap = abs(close - previous) + .14
        bar.update({"open": previous, "close": close,
                    "high": max(previous, close) + gap * .1,
                    "low": min(previous, close) - gap * .1,
                    "spread_bps": 4.5})
        previous = close
        for key in ("t", "available_at"):
            bar[key] = (datetime.fromisoformat(bar[key]) + timedelta(days=days)).isoformat()
    return unseen


class IndependentOosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = fixture.market_data()
        cls.report = oos.foundry.invent(cls.train, seed=173, max_trials=64, cost_bps=2.0)
        cls.unseen = unseen_period(cls.train)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name) / "private"
        self.parent.mkdir(mode=0o700)
        self.journal = self.parent / "one-shot-unseen.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_candidates_tested_with_no_order_eligibility(self):
        result = oos.assess(self.report, self.train, self.unseen)
        self.assertEqual(result["status"], "INDEPENDENT_DIAGNOSTICS_NOT_TRADING_VALIDATION")
        self.assertEqual(result["real_orders"], 0)
        self.assertEqual(result["public_signals"], 0)
        self.assertFalse(result["broker_eligible"])
        self.assertEqual(len(result["candidates"]), len(self.report["birth_certificates"]))
        self.assertEqual(result["familywise_hypotheses_count"],
                         self.report["multiple_testing_gate"]["total_search_attempts"])
        for candidate in result["candidates"]:
            self.assertFalse(candidate["broker_eligible"])
            self.assertGreaterEqual(candidate["familywise_bonferroni_bound_diagnostic"],
                                    candidate["iid_sign_bound_diagnostic"])
        self.assertEqual(result["receipt_sha256"], oos.foundry.digest(
            {k: v for k, v in result.items() if k != "receipt_sha256"}))

    def test_overlapping_or_unpurged_period_rejected(self):
        immediate = unseen_period(self.train, days=0)
        with self.assertRaisesRegex(oos.ValidationReject, "unseen_overlap_or_embargo"):
            oos.assess(self.report, self.train, immediate)
        close = copy.deepcopy(self.unseen)
        base = datetime.fromisoformat(self.train["bars"][-1]["available_at"]) + timedelta(minutes=5)
        first = datetime.fromisoformat(close["bars"][0]["t"])
        offset = base - first
        for row in close["bars"]:
            for field in ("t", "available_at"):
                row[field] = (datetime.fromisoformat(row[field]) + offset).isoformat()
        with self.assertRaisesRegex(oos.ValidationReject, "unseen_overlap_or_embargo"):
            oos.assess(self.report, self.train, close)

    def test_retimestamped_training_candles_are_not_independent(self):
        disguised = copy.deepcopy(self.train)
        disguised["source_id"] = "purported-new-provider"
        for bar in disguised["bars"]:
            for key in ("t", "available_at"):
                bar[key] = (datetime.fromisoformat(bar[key]) + timedelta(days=40)).isoformat()
        with self.assertRaisesRegex(oos.ValidationReject, "suspected_replayed_training_candles"):
            oos.assess(self.report, self.train, disguised)

    def test_cross_market_mismatch_rejected(self):
        changed = copy.deepcopy(self.unseen)
        changed["symbol"] = "EUR/USD"
        with self.assertRaisesRegex(oos.ValidationReject, "cross_symbol_or_interval"):
            oos.assess(self.report, self.train, changed)

    def test_too_few_bars_rejected(self):
        changed = copy.deepcopy(self.unseen)
        changed["bars"] = changed["bars"][:120]
        with self.assertRaisesRegex(oos.ValidationReject, "unseen_interval_too_short"):
            oos.assess(self.report, self.train, changed)

    def test_tampered_birth_rejected_even_when_report_checksum_recomputed(self):
        changed = copy.deepcopy(self.report)
        changed["birth_certificates"][0]["program"]["side"] = "SELL" if (
            changed["birth_certificates"][0]["program"]["side"] == "BUY") else "BUY"
        changed["report_sha256"] = oos.foundry.digest(
            {k: v for k, v in changed.items() if k != "report_sha256"})
        with self.assertRaisesRegex(oos.ValidationReject, "candidate_provenance_invalid"):
            oos.assess(changed, self.train, self.unseen)

    def test_falsified_multiple_testing_count_rejected_with_valid_checksum(self):
        changed = copy.deepcopy(self.report)
        changed["multiple_testing_gate"]["total_search_attempts"] = 1
        changed["report_sha256"] = oos.foundry.digest(
            {k: v for k, v in changed.items() if k != "report_sha256"})
        with self.assertRaisesRegex(oos.ValidationReject, "candidate_search_accounting_inconsistent"):
            oos.assess(changed, self.train, self.unseen)

    def test_training_dataset_digest_mismatch_rejected(self):
        changed = copy.deepcopy(self.train)
        changed["bars"][100]["close"] += 0.1
        with self.assertRaisesRegex(oos.ValidationReject, "training_dataset_or_statistical_gate_mismatch"):
            oos.assess(self.report, changed, self.unseen)

    def test_one_shot_ledger_is_idempotent_with_0600_mode(self):
        first = oos.validate_once(self.report, self.train, self.unseen, self.journal)
        self.assertEqual(first, oos.validate_once(self.report, self.train, self.unseen, self.journal))
        self.assertEqual(first["ledger_sequence"], 1)
        self.assertEqual(len(self.journal.read_text().splitlines()), 1)
        self.assertEqual(stat.S_IMODE(self.journal.stat().st_mode), 0o600)

    def test_retesting_same_report_on_new_holdout_forbidden(self):
        oos.validate_once(self.report, self.train, self.unseen, self.journal)
        different = unseen_period(self.train, days=30)
        with self.assertRaisesRegex(oos.ValidationReject, "holdout_reuse_different_dataset_prohibited"):
            oos.validate_once(self.report, self.train, different, self.journal)
        self.assertEqual(len(self.journal.read_text().splitlines()), 1)

    def test_corrupt_journal_rejected_without_replacing_receipt(self):
        oos.validate_once(self.report, self.train, self.unseen, self.journal)
        record = json.loads(self.journal.read_text())
        record["receipt"]["broker_eligible"] = True
        self.journal.write_text(json.dumps(record) + "\n")
        with self.assertRaisesRegex(oos.ValidationReject, "journal_checksum_invalid"):
            oos.validate_once(self.report, self.train, self.unseen, self.journal)

    def test_concurrent_same_holdout_cannot_multiply_experiments(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(lambda _: oos.validate_once(
                self.report, self.train, self.unseen, self.journal), range(6)))
        self.assertEqual({v["ledger_entry_sha256"] for v in outcomes},
                         {outcomes[0]["ledger_entry_sha256"]})
        self.assertEqual(len(self.journal.read_text().splitlines()), 1)

    def test_unsafe_directory_refused_without_writing(self):
        unsafe = Path(self.tmp.name) / "shared"
        unsafe.mkdir(mode=0o755)
        path = unsafe / "unsafe.jsonl"
        with self.assertRaisesRegex(oos.ValidationReject, "private_ledger_directory_required"):
            oos.validate_once(self.report, self.train, self.unseen, path)
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
