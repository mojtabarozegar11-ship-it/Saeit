"""Synthetic-only dependence sensitivity and frozen independent OOS tests."""

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "scripts" / "mojtrade_dependency_diagnostics.py"
if not SRC.is_file():
    SRC = HERE / "mojtrade_dependency_diagnostics.py"
sys.path.insert(0, str(SRC.parent))
sys.path.insert(0, str(HERE))
import test_mojtrade_independent_validation as prior

spec = importlib.util.spec_from_file_location("mojtrade_dependency_diagnostics", SRC)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class DependentDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = prior.fixture.market_data()
        cls.report = prior.oos.foundry.invent(cls.train, seed=173, max_trials=64, cost_bps=2.0)
        cls.unseen = prior.unseen_period(cls.train)
        cls.freeze = prior.oos.assess(cls.report, cls.train, cls.unseen)

    def test_independent_receipt_unchanged_and_zero_orders(self):
        reference = copy.deepcopy(self.freeze)
        response = audit.audit(self.report, self.train, self.unseen, self.freeze)
        self.assertEqual(self.freeze, reference)
        self.assertEqual(response["real_orders"], 0)
        self.assertEqual(response["public_signals"], 0)
        self.assertFalse(response["broker_eligible"])
        self.assertEqual(response["frozen_oos_receipt_sha256"], self.freeze["receipt_sha256"])
        self.assertEqual(response["receipt_sha256"], prior.oos.foundry.digest(
            {key: value for key, value in response.items() if key != "receipt_sha256"}))

    def test_all_frozen_candidates_share_fixed_block_grid(self):
        report = audit.audit(self.report, self.train, self.unseen, self.freeze)
        self.assertEqual(report["family_size"], len(self.report["birth_certificates"]))
        self.assertEqual(report["fixed_block_lengths_bars"], [8, 16, 32])
        self.assertEqual(report["fixed_resamples_per_block"], 256)
        self.assertEqual(report["other_prior_search_attempts"] + report["family_size"],
                         self.freeze["familywise_hypotheses_count"])
        for row in report["candidates"]:
            ps = row["max_family_one_sided_p_by_block_DIAGNOSTIC_ONLY"]
            self.assertEqual(set(ps), {"8", "16", "32"})
            self.assertEqual(row["worst_block_sensitivity_DIAGNOSTIC_ONLY"], max(ps.values()))
            self.assertTrue(all(0 < p <= 1 for p in ps.values()))

    def test_deterministic_on_frozen_inputs(self):
        a = audit.audit(self.report, self.train, self.unseen, self.freeze)
        b = audit.audit(self.report, self.train, self.unseen, self.freeze)
        self.assertEqual(a, b)

    def test_tampered_frozen_receipt_refused(self):
        altered = copy.deepcopy(self.freeze)
        altered["broker_eligible"] = True
        with self.assertRaisesRegex(audit.DependencyReject, "frozen_oos_receipt_not_identical"):
            audit.audit(self.report, self.train, self.unseen, altered)

    def test_retimestamped_training_dataset_rejected_by_independent_gate(self):
        suspicious = copy.deepcopy(self.train)
        suspicious["source_id"] = "changed-label"
        from datetime import datetime, timedelta
        for row in suspicious["bars"]:
            for name in ("t", "available_at"):
                row[name] = (datetime.fromisoformat(row[name]) + timedelta(days=30)).isoformat()
        with self.assertRaisesRegex(audit.oos.ValidationReject, "suspected_replayed_training_candles"):
            audit.audit(self.report, self.train, suspicious, self.freeze)

    def test_cross_candidate_shared_path_preserves_identical_series(self):
        n = 300
        market = [0.002 if i % 17 == 0 else (-0.001 if i % 19 == 0 else 0.0)
                  for i in range(n)]
        bounds = audit._max_family_null([market, list(market)], "frozen-report")
        for block in ("8", "16", "32"):
            self.assertEqual(bounds[block][0], bounds[block][1])

    def test_empty_family_no_fake_significance(self):
        self.assertEqual(audit._max_family_null([], "empty-family"), {})

    def test_nonmonotone_or_duplicate_exit_rejected(self):
        outcomes = [{"exit_index": 20, "net_return": 0.01},
                    {"exit_index": 20, "net_return": 0.02}]
        with self.assertRaisesRegex(audit.DependencyReject, "invalid_or_overlapping_simulated_exit"):
            audit._realized_bar_series(outcomes, 300)

    def test_offline_cli_freezes_first_dataset_and_prints_no_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "private"
            private.mkdir(mode=0o700)
            artifacts = []
            for label, contents in (("foundry", self.report), ("training", self.train),
                                    ("unseen", self.unseen)):
                path = root / (label + ".json")
                path.write_text(json.dumps(contents), encoding="utf-8")
                artifacts.append(str(path))
            ledger = private / "holdout.jsonl"
            args = ["--foundry-report", artifacts[0], "--training-data", artifacts[1],
                    "--unseen-data", artifacts[2], "--private-ledger", str(ledger)]
            outputs = []
            for _ in range(2):
                stream = io.StringIO()
                with redirect_stdout(stream):
                    self.assertEqual(audit.main(args), 0)
                outputs.append(json.loads(stream.getvalue()))
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(outputs[0]["real_orders"], 0)
            self.assertEqual(outputs[0]["public_signals"], 0)
            self.assertEqual(len(ledger.read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
