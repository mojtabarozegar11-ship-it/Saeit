"""Stage-5 actual bilingual draft bytes and fail-closed expert review handoff."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
def source_module(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

stage34 = source_module(ROOT / "scripts/factory_stage34_autonomous_handoff_20261023.py", "stage34_for_stage5_tests")
stage5 = source_module(ROOT / "scripts/factory_stage5_evidence_workbook_20261023.py", "stage5_under_test")
prior_tests = source_module(ROOT / "tests/test_factory_stage34_autonomous_handoff_20261023.py", "stage34_fixture_for_stage5")


class Stage5Proof(unittest.TestCase):
    def setUp(self):
        self.fixture = prior_tests.Stage34Tests(methodName="test_both_stages_progress_with_real_evidence_and_no_public_claim")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.area = self.fixture.area
        self.name = self.fixture.name
        self.assertEqual(stage34.execute(self.root)["stage4_new"], 1)

    def read(self, location):
        return json.loads((self.area / location / self.name).read_text(encoding="utf-8"))

    def test_round_robin_fairness_over_batch_limit(self):
        names = ["order-a", "order-b", "order-c"]
        seen = []
        for _ in range(6):
            selected, path, state = stage5.fair_batch(self.area, names, 1, stage34)
            seen.extend(selected)
            stage34.atomic(path, state)
        self.assertEqual(seen, names + names)
        self.assertEqual(stage34.read(path)["next_index"], 0)
        self.assertEqual(stage5.fair_batch(self.area, names, 5, stage34)[0], names)

    def test_corrupt_cursor_fails_closed(self):
        cursor = self.area / "stage-05/round-robin-cursor.json"
        stage34.atomic(cursor, {"schema": "saeit.factory.stage5.round-robin.v1", "next_index": -1})
        with self.assertRaisesRegex(RuntimeError, "STAGE5_CURSOR_INVALID"):
            stage5.fair_batch(self.area, ["order-a"], 1, stage34)

    def test_actual_draft_and_stage6_independent_review_queue(self):
        result = stage5.execute(self.root, stage34)
        self.assertEqual(result["stage5_created_this_tick"], 1)
        self.assertEqual(result["stage5_drafts_total"], 1)
        self.assertEqual(result["stage6_review_queue"], 1)
        self.assertEqual(result["quality1000_certifications_created"], 0)
        self.assertFalse(result["websites_modified"])
        manifest = self.read("stage-05/completed-drafts")
        review = self.read("stage-06/inbox")
        receipt = self.read("stage-05/receipts")
        self.assertEqual(review["stage5_manifest_sha256"], stage34.digest(manifest))
        self.assertEqual(receipt["stage6_review_packet_sha256"], stage34.digest(review))
        self.assertEqual(set(manifest["manuscript_sha256"]), {"fa-IR", "en-US"})
        self.assertFalse(review["human_review_completed"])
        self.assertFalse(review["reviewer_signature_created"])
        self.assertFalse(manifest["quality1000_approved"])
        for loc in ("fa-IR", "en-US"):
            relative = manifest["manuscript_files"][loc]
            body = (self.area / "stage-05/drafts" / relative).read_bytes()
            self.assertEqual(stage5.sha_bytes(body), manifest["manuscript_sha256"][loc])
            self.assertGreater(len(body.decode("utf-8").split()), 1000)
            self.assertEqual(sum(line.startswith("## ") for line in body.decode("utf-8").splitlines()), 7)
        self.assertIn("تمرین و کلید پاسخ", (self.area / "stage-05/drafts" / (self.name[:-5]) / "fa-IR.md").read_text())

    def test_rerun_idempotent_no_duplicate_approval(self):
        first = stage5.execute(self.root, stage34)
        self.assertEqual(first["stage5_created_this_tick"], 1)
        second = stage5.execute(self.root, stage34)
        self.assertEqual(second["stage5_created_this_tick"], 0)
        self.assertEqual(second["stage6_review_queue"], 1)
        self.assertEqual(second["quality1000_certifications_created"], 0)

    def test_tampered_prior_stage_blocks_without_handoff(self):
        target = self.area / "stage-04/completed-prototypes" / self.name
        obj = json.loads(target.read_text())
        obj["bilingual_sample_activities"][0]["prototype_en"] = "unauthorized alteration"
        stage34.atomic(target, obj)
        r = stage5.execute(self.root, stage34)
        self.assertEqual(r["stage5_blocked_this_tick"], 1)
        self.assertEqual(r["stage6_review_queue"], 0)
        self.assertFalse((self.area / "stage-05/completed-drafts" / self.name).exists())

    def test_missing_source_link_blocks_before_writing(self):
        target = self.area / "stage-03/completed-designs" / self.name
        obj = json.loads(target.read_text())
        obj["chapters"][0]["source_ids"] = ["spoofed-source"]
        stage34.atomic(target, obj)
        r = stage5.execute(self.root, stage34)
        self.assertEqual(r["stage5_blocked_this_tick"], 1)
        self.assertEqual(r["stage6_review_queue"], 0)

    def test_draft_tampering_never_silently_overwritten(self):
        stage5.execute(self.root, stage34)
        target = self.area / "stage-05/drafts" / (self.name[:-5]) / "en-US.md"
        target.write_text("replacement", encoding="utf-8")
        r = stage5.execute(self.root, stage34)
        self.assertEqual(r["stage5_blocked_this_tick"], 1)
        self.assertEqual(target.read_text(), "replacement")
        self.assertEqual(r["quality1000_certifications_created"], 0)

    def test_unsafe_symlink_input_cannot_advance(self):
        target = self.area / "stage-05/inbox" / self.name
        target.unlink()
        target.symlink_to(self.area / "stage-04/inbox" / self.name)
        r = stage5.execute(self.root, stage34)
        self.assertEqual(r["stage5_created_this_tick"], 0)
        self.assertEqual(r["stage6_review_queue"], 0)


if __name__ == "__main__":
    unittest.main()
