"""No-network research accounting: reconcile slots with hypothetical fills."""

import copy
import importlib.util
import json
import os
import sqlite3
import stat
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "mojtrade_unified_shadow.py"
if not MODULE.is_file():
    MODULE = Path(__file__).with_name("mojtrade_unified_shadow.py")
sys.path.insert(0, str(MODULE.parent))
SHADOW_FIXTURE = ROOT / "tests" / "test_mojtrade_unified_shadow.py"
if not SHADOW_FIXTURE.is_file():
    SHADOW_FIXTURE = Path(__file__).with_name("test_mojtrade_unified_shadow.py")
spec = importlib.util.spec_from_file_location("reconciliation_unified_fixture", SHADOW_FIXTURE)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
shadow = fixture.shadow
reconcile = shadow.reconciliation


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.private = Path(self.tmp.name) / "private"
        self.private.mkdir(mode=0o700)
        self.packet, self.now = fixture.packet()

    def tearDown(self):
        self.tmp.cleanup()

    def run_chain(self):
        return shadow.run_shadow(self.packet, self.private, now=self.now)

    def test_research_filled_reconciled_and_idempotent_chain(self):
        first = self.run_chain()
        rec = first["reconciliation"]
        self.assertEqual(rec["receipt"]["status"], "SIMULATED_FILLED")
        self.assertFalse(rec["receipt"]["broker_exposure_verified"])
        self.assertEqual(rec["receipt"]["risk_reservation"], "REMAINS_RESERVED")
        self.assertFalse(rec["receipt"]["release_eligible"])
        self.assertEqual(rec["sequence"], 1)
        path = self.private / "unified-replay-reconciliation.jsonl"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(reconcile.verify_log(path), 1)
        self.assertEqual(first, self.run_chain())
        self.assertEqual(reconcile.verify_log(path), 1)

    def test_zero_fill_remains_risk_reserved(self):
        self.packet["execution_book"]["events"][1]["venue_status"] = "HALT"
        result = self.run_chain()
        receipt = result["reconciliation"]["receipt"]
        self.assertEqual(receipt["status"], "SIMULATED_UNFILLED")
        self.assertEqual(receipt["simulated_filled_quantity"], "0")
        self.assertFalse(receipt["release_eligible"])
        with sqlite3.connect(self.private / "unified-portfolio-risk.sqlite3") as con:
            self.assertGreater(float(con.execute("SELECT approved_risk FROM decisions").fetchone()[0]), 0)

    def test_tampered_fill_hash_rejected(self):
        result = self.run_chain()
        twin = copy.deepcopy(result["execution_twin"])
        twin["receipts"][0]["filled_quantity"] = "2"
        twin["report_sha256"] = reconcile._digest({k: v for k, v in twin.items() if k != "report_sha256"})
        with self.assertRaisesRegex(reconcile.ReconciliationReject, "twin_fill_hash_invalid"):
            reconcile.build_receipt(result["risk_handoff"], twin)

    def test_rehashed_but_mismatched_request_refused(self):
        result = self.run_chain()
        hand = copy.deepcopy(result["risk_handoff"])
        risk = hand["risk_response"]
        decision = risk["decisions"][0]
        decision["request_id"] = "MTB-injected-mismatch"
        decision["receipt_sha256"] = reconcile._digest({k: v for k, v in decision.items() if k != "receipt_sha256"})
        risk["report_sha256"] = reconcile._digest({k: v for k, v in risk.items() if k != "report_sha256"})
        hand["handoff_sha256"] = reconcile._digest({k: v for k, v in hand.items() if k != "handoff_sha256"})
        with self.assertRaisesRegex(reconcile.ReconciliationReject, "risk_twin_lineage_mismatch"):
            reconcile.build_receipt(hand, result["execution_twin"])

    def test_same_request_conflicting_hypothetical_fill_fails_closed(self):
        result = self.run_chain()
        twin = copy.deepcopy(result["execution_twin"])
        fill = twin["receipts"][0]
        fill["status"] = "NO_EXECUTABLE_EVENT"
        fill["filled_quantity"] = "0"
        fill["cancelled_quantity"] = fill["requested_quantity"]
        fill["average_fill_price"] = None
        fill["partial_fills"] = []
        fill["receipt_sha256"] = reconcile._digest({k: v for k, v in fill.items() if k != "receipt_sha256"})
        twin["report_sha256"] = reconcile._digest({k: v for k, v in twin.items() if k != "report_sha256"})
        with self.assertRaisesRegex(reconcile.ReconciliationReject, "conflicting_reconciliation"):
            reconcile.record_receipt(result["risk_handoff"], twin,
                                     self.private / "unified-replay-reconciliation.jsonl")

    def test_journal_tamper_detected(self):
        self.run_chain()
        journal = self.private / "unified-replay-reconciliation.jsonl"
        data = json.loads(journal.read_text())
        data["receipt"]["release_eligible"] = True
        journal.write_text(json.dumps(data) + "\n")
        with self.assertRaisesRegex(reconcile.ReconciliationReject, "journal_receipt_hash_invalid"):
            reconcile.verify_log(journal)

    def test_strict_private_permissions_and_no_symlink(self):
        result = self.run_chain()
        unsafe = Path(self.tmp.name) / "unsafe"
        unsafe.mkdir(mode=0o755)
        with self.assertRaisesRegex(reconcile.ReconciliationReject, "private_parent"):
            reconcile.record_receipt(result["risk_handoff"], result["execution_twin"], unsafe / "a.jsonl")
        path = self.private / "shortcut.jsonl"
        path.symlink_to(self.private / "unified-replay-reconciliation.jsonl")
        with self.assertRaisesRegex(reconcile.ReconciliationReject, "private_parent_or_symlink"):
            reconcile.record_receipt(result["risk_handoff"], result["execution_twin"], path)

    def test_concurrent_identical_receipts_create_only_one_row(self):
        result = self.run_chain()
        path = self.private / "unified-replay-reconciliation.jsonl"
        with ThreadPoolExecutor(max_workers=5) as pool:
            records = list(pool.map(lambda _: reconcile.record_receipt(
                result["risk_handoff"], result["execution_twin"], path), range(12)))
        self.assertEqual({x["entry_sha256"] for x in records}, {records[0]["entry_sha256"]})
        self.assertEqual(reconcile.verify_log(path), 1)


if __name__ == "__main__":
    unittest.main()
