"""Evidence-bound, offline regression tests for MojPlayWin private evolution."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mpw_v91_port import evolution as e


class EvolutionTests(unittest.TestCase):
    def test_empty_dataset_never_claims_upgrade(self):
        result = e.calculate([], None, {"state": "unavailable", "routes_checked": 0})
        self.assertEqual(result["master_generation"], 64)
        self.assertEqual(result["active_policy"], "baseline")
        self.assertEqual(result["decision"], "insufficient_verified_outcomes")
        self.assertEqual(result["verified_outcome_count"], 0)
        for key in ("self_modified_code", "auto_published", "shared_runtime_modified"):
            self.assertIs(result[key], False)
        self.assertEqual(result["executed_financial_actions"], 0)

    def test_policy_improves_when_benchmark_proves_fewer_false_positives(self):
        rows = [{"id": str(i), "kind": "research_digest", "quality": 92.0,
                 "source_count": 1, "ready": False} for i in range(12)]
        policy, metrics, reason = e._compare(rows, "baseline")
        self.assertEqual(policy, "source_rigorous")
        self.assertEqual(metrics["baseline"]["false_positive"], 12)
        self.assertEqual(metrics["source_rigorous"]["false_positive"], 0)
        self.assertEqual(reason, "private_policy_improved_on_verified_outcomes")

    def test_upgrade_requires_twelve_verified_outcomes(self):
        rows = [{"id": str(i), "kind": "research_digest", "quality": 92.0,
                 "source_count": 1, "ready": False} for i in range(11)]
        self.assertEqual(e._compare(rows, "baseline")[0], "baseline")

    def test_no_unjustified_upgrade(self):
        rows = [{"id": str(i), "kind": "product_blueprint", "quality": 98.0,
                 "source_count": 3, "ready": True} for i in range(18)]
        policy, metrics, reason = e._compare(rows, "baseline")
        self.assertEqual(policy, "baseline")
        self.assertEqual(reason, "no_proven_policy_improvement")

    def test_new_outcomes_are_deduplicated_and_history_is_bounded(self):
        rows = [{"id": "verified-1", "kind": "research_digest", "quality": 60,
                 "source_count": 1, "ready": False}]
        old = {"epoch": 14, "active_policy": "baseline",
               "seen_ids": ["verified-1"],
               "history": [{"epoch": i} for i in range(105)]}
        result = e.calculate(rows, old, {"state": "observed", "routes_checked": 11})
        self.assertEqual(result["epoch"], 15)
        self.assertEqual(result["new_verified_outcomes"], 0)
        self.assertLessEqual(len(result["history"]), e.MAX_HISTORY)

    def test_private_json_rejects_links_oversize_and_invalid(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            valid = root / "valid.json"
            valid.write_text('{"tenant":"mojplaywin-main"}', encoding="utf-8")
            self.assertIsNotNone(e._json(valid))
            (root / "link.json").symlink_to(valid)
            self.assertIsNone(e._json(root / "link.json"))
            (root / "large.json").write_text("x" * (e.MAX_READ + 1))
            self.assertIsNone(e._json(root / "large.json"))
            (root / "bad.json").write_text("{not valid}")
            self.assertIsNone(e._json(root / "bad.json"))

    def test_draft_and_review_must_match_source_and_tenant(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state"
            state.mkdir(mode=0o700)
            for name in ("processed", "drafts", "quality_reviews"):
                (state / name).mkdir(parents=True, mode=0o700)
            payload = {"tenant": e.TENANT, "review_only": True, "kind": "research_digest"}
            raw = json.dumps(payload).encode()
            processed = state / "processed" / "brief.json"
            processed.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()[:24]
            draft = state / "drafts" / (digest + ".json")
            review = state / "quality_reviews" / (digest + ".json")
            draft.write_text(json.dumps({"draft": {
                "tenant": e.TENANT, "published": False, "sources": ["https://example.org"]}}))
            review.write_text(json.dumps({"tenant": e.TENANT,
                "quality_score": 91,
                "status": "needs_editorial_revision"}))
            with patch.object(e, "AGENT_STATE", state):
                rows = e._scored_reviews()
                self.assertEqual(len(rows), 1)
                self.assertIs(rows[0]["ready"], False)
                review.write_text(json.dumps({"tenant": "zomorodmelal",
                    "quality_score": 98, "status": "review_ready_not_published"}))
                self.assertEqual(e._scored_reviews(), [])

    def test_benchmark_penalizes_unsafe_acceptance(self):
        rows = [{"id": str(i), "kind": "research_digest", "quality": 91,
                 "source_count": 1, "ready": False} for i in range(5)]
        base = e._benchmark(rows, 90, 1)
        strict = e._benchmark(rows, 95, 2)
        self.assertLess(base["utility"], strict["utility"])


if __name__ == "__main__":
    unittest.main()
