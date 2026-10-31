"""Isolated QA for the private proposal register; no production data or network."""
import csv
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "zomorod_project_approval_snapshot.py"
spec = importlib.util.spec_from_file_location("zm_approvals", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

FIELDS = [
    "source_id", "external_key", "title_or_subject", "official_title_verified",
    "decision", "execution_state", "planned_operational_jobs",
    "actual_employees_hired", "owner", "classification_or_parent",
    "budget_irr", "accounting_document_created", "source_evidence",
]


def fixture():
    rows = []
    for source_id, decision, jobs in [
        ("1", "approved", "5.0"), ("2", "approved", "0.0"),
        ("3", "rejected", ""), ("4", "undetermined", ""),
        ("142", "approved", "0.0"),
    ]:
        rows.append({
            "source_id": source_id,
            "external_key": "ZM-" + source_id.zfill(3),
            "title_or_subject": "Synthetic proposal " + source_id,
            "official_title_verified": "True",
            "decision": decision,
            "execution_state": "planned" if decision == "approved" else "not_approved",
            "planned_operational_jobs": jobs,
            "actual_employees_hired": "",
            "owner": "Synthetic owner",
            "classification_or_parent": "Synthetic",
            "budget_irr": "",
            "accounting_document_created": "False",
            "source_evidence": "Synthetic only",
        })
    return rows


class ApprovalSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zm-approvals-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.csv = self.root / "sample.csv"
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)

    def write(self, rows):
        with self.csv.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def test_summary_and_repeat_install(self):
        self.write(fixture())
        snapshot = module.parse_csv(self.csv)
        self.assertEqual(snapshot["summary"]["records"], 5)
        self.assertEqual(snapshot["summary"]["approved"], 3)
        self.assertEqual(snapshot["summary"]["rejected"], 1)
        self.assertEqual(snapshot["summary"]["undetermined"], 1)
        self.assertEqual(snapshot["summary"]["planned_operational_jobs"], 5)
        self.assertEqual(snapshot["summary"]["actual_employees_hired"], None)
        self.assertEqual(snapshot["summary"]["decision_review_flags"], 1)
        output = self.private / "approvals_snapshot.json"
        self.assertFalse(output.exists())
        self.assertEqual(module.install(snapshot, output), "INSTALLED")
        self.assertEqual(module.install(snapshot, output), "ALREADY_INSTALLED")
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_reject_duplicate_key(self):
        rows = fixture()
        rows.append(dict(rows[0]))
        self.write(rows)
        with self.assertRaises(ValueError):
            module.parse_csv(self.csv)

    def test_reject_unapproved_jobs_and_financial_values(self):
        rows = fixture()
        rows[2]["planned_operational_jobs"] = "5.0"
        self.write(rows)
        with self.assertRaises(ValueError):
            module.parse_csv(self.csv)
        rows = fixture()
        rows[0]["budget_irr"] = "1000"
        self.write(rows)
        with self.assertRaises(ValueError):
            module.parse_csv(self.csv)

    def test_reject_unverified_current_snapshot_replacement(self):
        self.write(fixture())
        first = module.parse_csv(self.csv)
        target = self.private / "approvals_snapshot.json"
        self.assertEqual(module.install(first, target), "INSTALLED")
        rows = fixture()
        rows[0]["planned_operational_jobs"] = "6.0"
        self.write(rows)
        with self.assertRaises(ValueError):
            module.install(module.parse_csv(self.csv), target)

    def test_cli_fail_closed_without_controls(self):
        self.write(fixture())
        target = self.private / "approvals_snapshot.json"
        rc = module.main([str(self.csv), "--install", "--output", str(target)])
        self.assertEqual(rc, 2)
        self.assertFalse(target.exists())
        rc = module.main([str(self.csv)])
        self.assertEqual(rc, 0)
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
