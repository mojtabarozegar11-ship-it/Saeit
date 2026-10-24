"""No fake release; owner rejection is all-or-nothing, hash-bound, and idempotent."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

SRC = Path(__file__).resolve().parents[1] / "scripts/factory_owner_reject_184_rework_20261024.py"
spec = importlib.util.spec_from_file_location("owner_rework", SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

PARAGRAPH = "This evidence workbook does not provide scientific findings for a farm and requires checking original full text against field conditions and local regulations before any practical agricultural recommendation."


class OwnerRejectTests(unittest.TestCase):
    def fixture(self, temp, count=2):
        root = Path(temp) / "private"
        area = root / "production-instructions"
        for name in ("stage-05/downloadable-receipts", "stage-05/completed-drafts",
                     "stage-05/downloadable-candidates", "stage-05/strict-qc-rework",
                     "stage-05/substantive-rework-inbox"):
            (area / name).mkdir(parents=True, exist_ok=True)
        for i in range(1, count+1):
            name = "WO-%08d--r001.json" % i
            stem = name[:-5]
            manifest = {"order_id": "WO-%08d" % i,
                        "draft_kind": "original_bilingual_evidence_method_workbook"}
            fa = en = ("\n\n".join([PARAGRAPH]*4)).encode()
            files = {"README.md": b"draft", "index.html": b"<html>draft</html>",
                     "fa-IR.md": fa, "en-US.md": en, "sources.json": b"[]",
                     "integrity.json": b"{}"}
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                for fn, val in files.items():
                    z.writestr("agri-"+stem+"/"+fn, val)
            raw = archive.getvalue()
            rel = "stage-05/downloadable-candidates/"+stem+"/navigator.zip"
            target = area / rel
            target.parent.mkdir(parents=True)
            target.write_bytes(raw)
            (area / "stage-05/completed-drafts" / name).write_text(json.dumps(manifest))
            receipt = {"order_id": manifest["order_id"],
                       "stage5_manifest_sha256": m.sha(m.canonical(manifest).rstrip(b"\n")),
                       "archive_relative_path": rel,
                       "zip_sha256": m.sha(raw), "zip_bytes": len(raw),
                       "scientific_quality_certified": False,
                       "ready_for_paid_store": False,
                       "public_distribution_allowed": False}
            (area / "stage-05/downloadable-receipts" / name).write_text(json.dumps(receipt))
            (area / "stage-05/strict-qc-rework" / name).write_text(
                json.dumps({"must_resubmit_new_artifact_and_repeat_strict_qc": True}))
            (area / "stage-05/substantive-rework-inbox" / name).write_text("{}")
        return root, area

    def test_preflight_does_not_write_and_persist_is_immutable(self):
        with tempfile.TemporaryDirectory() as temp:
            root, area = self.fixture(temp)
            old = (area / "stage-05/downloadable-candidates/WO-00000001--r001/navigator.zip").read_bytes()
            pre = m.execute(root, expected=2, dry_run=True)
            self.assertEqual(pre["preflight_checked"], 2)
            self.assertFalse((area / "stage-05/owner-rework-20261024").exists())
            done = m.execute(root, expected=2)
            self.assertEqual(done["owner_rejected_and_returned"], 2)
            self.assertEqual(done["routing_existing_strict"], 2)
            self.assertEqual(done["routing_existing_substantive"], 2)
            self.assertEqual(m.execute(root, expected=2), done)
            self.assertEqual(old, (area / "stage-05/downloadable-candidates/WO-00000001--r001/navigator.zip").read_bytes())
            for packet in (area / "stage-05/owner-rework-20261024").glob("*.json"):
                data = json.loads(packet.read_text())
                self.assertFalse(data["quality1000_approved"])
                self.assertFalse(data["public_distribution_allowed"])
                self.assertEqual(data["owner_decision"], "REJECT_RETURN_TO_STAGE5_REWORK")

    def test_count_drift_fails_without_partial_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root, area = self.fixture(temp)
            with self.assertRaisesRegex(ValueError, "COHORT_COUNT_CHANGED"):
                m.execute(root, expected=184)
            self.assertFalse((area / "stage-05/owner-rework-20261024").exists())

    def test_tamper_and_hidden_releases_fail_before_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root, area = self.fixture(temp)
            name = "WO-00000002--r001.json"
            recpath = area / "stage-05/downloadable-receipts" / name
            rec = json.loads(recpath.read_text())
            rec["ready_for_paid_store"] = True
            recpath.write_text(json.dumps(rec))
            with self.assertRaisesRegex(ValueError, "RELEASE_FLAGS"):
                m.execute(root, expected=2)
            self.assertFalse((area / "stage-05/owner-rework-20261024").exists())

    def test_conflicting_existing_decision_must_not_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root, area = self.fixture(temp)
            m.execute(root, expected=2)
            item = area / "stage-05/owner-rework-20261024/WO-00000001--r001.json"
            data = json.loads(item.read_text())
            data["quality1000_approved"] = True
            item.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "OWNER_REJECTION_CONFLICT"):
                m.execute(root, expected=2)


if __name__ == "__main__":
    unittest.main()
