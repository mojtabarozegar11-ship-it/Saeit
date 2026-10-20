"""V3 private research triage: real non-overlap and path safety tests."""
import fcntl
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from factory_research_triage_locked_v3 import locked_snapshot


class ResearchTriageLockContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "factory-private"
        self.root.mkdir()
        self.ledger = self.root / "research-rework" / "product-1"
        self.ledger.mkdir(parents=True)
        self.source = self.ledger / "ledger.json"
        self.source.write_text(json.dumps({
            "schema": "saeit.factory.research-rework.v1",
            "product_id": 1,
            "current_status": "research_correction_required",
            "history": [{
                "fingerprint": "a" * 64,
                "blocking_reasons": [
                    "FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED"
                ]
            }]
        }), encoding="utf8")

    def test_serialized_private_plan_and_idempotency(self):
        original = self.source.read_bytes()
        first = locked_snapshot(self.root)
        self.assertEqual(first["workplans_created_or_updated"], 1)
        inbox = self.root / "research-triage"
        lock = inbox / ".v3-research-triage.lock"
        self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o600)
        plan = json.loads((inbox / "product-1.json").read_text())
        self.assertFalse(plan["commercial_approval_claimed"])
        self.assertFalse(plan["research_evidence_confirmed_complete"])
        self.assertEqual(locked_snapshot(self.root)["workplans_created_or_updated"], 0)
        self.assertEqual(self.source.read_bytes(), original)

    def test_second_run_fails_closed_while_first_holds_lock(self):
        inbox = self.root / "research-triage"
        inbox.mkdir()
        lock = inbox / ".v3-research-triage.lock"
        with lock.open("a+b") as held:
            fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "V3_TRIAGE_ALREADY_RUNNING"):
                locked_snapshot(self.root)
            self.assertFalse((inbox / "triage-status.json").exists())
        self.assertEqual(locked_snapshot(self.root)["workplans_created_or_updated"], 1)

    def test_lock_symlink_never_follows_external_file(self):
        inbox = self.root / "research-triage"
        inbox.mkdir()
        outside = self.root / "external.txt"
        outside.write_text("untouched", encoding="utf8")
        (inbox / ".v3-research-triage.lock").symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, "V3_TRIAGE_LOCK_SYMLINK"):
            locked_snapshot(self.root)
        self.assertEqual(outside.read_text(encoding="utf8"), "untouched")
        self.assertFalse((inbox / "triage-status.json").exists())

    def test_root_symlink_is_denied(self):
        alias = self.root.parent / "factory-alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "V3_TRIAGE_ROOT_UNSAFE"):
            locked_snapshot(alias)


if __name__ == "__main__":
    unittest.main()
