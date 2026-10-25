"""Regression for safe legacy cron migration without collateral factory stops."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "deploy/install_factory_strict_serial_fullcycle_v1.sh"
RAW = SCRIPT.read_text(encoding="utf8")
TRANSFORM = RAW.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
OPS = "/home/githubops/factory-runtime/operations/production-instructions/"
NEW = "SAEIT_STRICT_SERIAL_PRODUCT_TO_QC1000_20261025"
LEGACY = ["SAEIT_SEQUENTIAL_SCIENCE_CASEWORK_20261025",
          "SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1",
          "SAEIT_AGRI200_STRICT_QC1000_V1",
          "SAEIT_FACTORY_STAGE2_SOURCE_DISCOVERY_V1",
          "SAEIT_QC184_LICENSED_ALTERNATIVE_DISCOVERY_20261024",
          "SAEIT_QC_V003_DOCTORAL_DEPTH_GATE_20261024",
          "SAEIT_QC_V003_SCIENTIFIC_REVIEW_HANDOFF_20261024"]
SHARED = ["SAEIT_FACTORY_STAGE2_RESEARCH_V1",
          "SAEIT_FACTORY_STAGE34_AUTONOMOUS_HANDOFF_V1",
          "SAEIT_FACTORY_STAGE5_EVIDENCE_WORKBOOK_V1",
          "SAEIT_FACTORY_STAGE5_SUBSTANTIVE_REWORK_V1",
          "SAEIT_FACTORY_STAGE6_PREFLIGHT_REWORK_V1",
          "SAEIT_SCIENCE_REWORK_ALL_20261024"]


class CronMigrationTests(unittest.TestCase):
    def transform(self, lines):
        with tempfile.TemporaryDirectory() as folder:
            before, after = (Path(folder) / x for x in ("before", "after"))
            before.write_text("\n".join(lines) + "\n")
            arguments = [str(before), str(after), NEW, *LEGACY,
                         "--SHARED-MARKERS--", *SHARED]
            with mock.patch.object(sys, "argv", ["cron_migration", *arguments]):
                exec(compile(TRANSFORM, "cron-migration", "exec"), {"__name__": "__main__"})
            return after.read_text().splitlines()

    def test_shared_workers_preserved_with_exclusion_and_other_lines_untouched(self):
        existing = (
            f"* * * * * python -B {OPS}stage2-research.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --batch 250"
            f" >> {OPS}stage2-research.log 2>&1 # {SHARED[0]}")
        old_agri = f"*/2 * * * * python -B {OPS}stage2-literature-scout.py >> {OPS}scout.log # {LEGACY[3]}"
        unrelated = "* * * * * /opt/other-family/worker # OTHER_FAMILY_KEEP"
        output = self.transform([existing, old_agri, unrelated])
        self.assertIn(f"{OPS}stage2-research-serial.py", output[0])
        self.assertIn("--exclude-owner-agri200 >>", output[0])
        self.assertIn("# PAUSED_BY_STRICT_SERIAL_20261025 "+old_agri, output)
        self.assertIn(unrelated, output)
        self.assertTrue(any(NEW in row and row.startswith("* * * * *") for row in output))
        self.assertEqual(self.transform(output), output)

    def test_unknown_shared_worker_aborts_without_touching_cron(self):
        unknown = f"* * * * * /opt/stranger.py >> /tmp/out.log # {SHARED[0]}"
        with self.assertRaisesRegex(SystemExit, "UNRECOGNIZED_SHARED_WORKER_CRON"):
            self.transform([unknown])

    def test_duplicate_active_cron_aborts(self):
        duplicate = f"* * * * * python -B {OPS}stage2-research.py >> {OPS}out.log # {SHARED[0]}"
        with self.assertRaisesRegex(SystemExit, "DUPLICATE_FACTORY_CRON"):
            self.transform([duplicate, duplicate])


if __name__ == "__main__":
    unittest.main()
