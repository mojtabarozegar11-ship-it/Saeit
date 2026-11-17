"""Check legacy production-backup destructive jobs remain fail-closed.

Pure offline source inspection. Never opens remote connections, SQL, backups,
environment secrets, and never modifies the runtime. This CI check signals
regressions; the repo must require the check in branch protection before it
can become a merge-blocking policy.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = {
    "zomorod-mysql-lossless-page-compression.yml": "compress",
    "zomorod-live-mysql-precompression-backup.yml": "inspect",
    "zomorod-relocate-verified-legacy-backups-20261104.yml": "inspect",
    "vps-controlled-old-sqlite-cleanup-20261107.yml": "cleanup",
    "zomorod-online-alter-probe-lock-none.yml": "inspect",
}

def job_block(content: str, expected: str) -> str:
    lines = content.splitlines()
    try:
        j = lines.index("jobs:")
    except ValueError as exc:
        raise AssertionError("No jobs section") from exc
    sections = {}
    active = None
    for line in lines[j + 1:]:
        name = re.fullmatch(r"  ([A-Za-z0-9_-]+):\s*", line)
        if name:
            active = name.group(1)
            sections[active] = []
            continue
        if active is not None:
            sections[active].append(line)
    if set(sections) != {expected}:
        raise AssertionError("Unexpected workflow jobs; require review of all gates")
    return "\n".join(sections[expected])

class LegacyFactoryBackupSafetyContract(unittest.TestCase):
    def test_all_four_destructive_or_quota_risk_jobs_remain_disabled(self):
        for filename, job in WORKFLOWS.items():
            with self.subTest(filename=filename):
                text = (ROOT / ".github/workflows" / filename).read_text(encoding="utf-8")
                section = job_block(text, job)
                self.assertRegex(section, r"(?m)^    if: false\s*$")
                # The hold must be a job-level condition preceding the runner,
                # rather than a comment or a step that is reached too late.
                self.assertLess(section.index("    if: false"), section.index("    runs-on:"))
                self.assertIn("permissions:\n  contents: read", text)

    def test_workflows_retain_expected_hazard_markers_not_a_hidden_replacement(self):
        p = ROOT / ".github/workflows"
        markers = {
            "zomorod-mysql-lossless-page-compression.yml": "ALTER TABLE ",
            "zomorod-live-mysql-precompression-backup.yml":
                 ".backups/mysql-precompression-20261018.sql.gz",
            "zomorod-relocate-verified-legacy-backups-20261104.yml":
                 "src.unlink()",
            "vps-controlled-old-sqlite-cleanup-20261107.yml":
                 "p.unlink()",
            "zomorod-online-alter-probe-lock-none.yml":
                 'sql("CREATE TABLE "',
        }
        for filename, marker in markers.items():
            with self.subTest(filename=filename):
                text = (p / filename).read_text(encoding="utf-8")
                self.assertIn(marker, text,
                     "Unexpected rewrite: review the new workflow and hazards")

    def test_source_readonly_admission_never_authorizes_cleanup(self):
        p = ROOT / "scripts/factory_recovery_destination_admission_readonly_20261117.py"
        text = p.read_text(encoding="utf-8")
        self.assertIn('"ready_to_export_live_data":False',text)
        self.assertIn('"ready_to_clean_live_database":False',text)
        self.assertIn('"files_created":0,"files_deleted":0',text)


HISTORICAL_EXPORT_HOLDS = {
    "zomorod-live-full-tables-archive-20261104.yml": {"backup"},
    "zomorod-live-segmented-archive-20261104.yml":
        {"schema", "chunks", "finalize"},
    "zomorod-agenttask-part6-recovery-20261104.yml": {"chunks"},
}

class HistoricalSqlArchiveNoDuplicateExport(unittest.TestCase):
    """All 3 legacy exporter workflows are read-only-inert until capacity exists."""
    def test_historical_exporters_are_fail_closed_on_every_job(self):
        for filename, expected_jobs in HISTORICAL_EXPORT_HOLDS.items():
            with self.subTest(workflow=filename):
                text=(ROOT/".github/workflows"/filename).read_text(encoding="utf-8")
                self.assertIn("permissions:\n  contents: read",text)
                self.assertIn("jobs:\n",text)
                after=text.split("jobs:\n",1)[1]
                split=re.split(r"(?m)^  ([a-zA-Z0-9_-]+):\s*\n",after)
                # [preamble, name, body, name, body, ...]
                found={split[i]:split[i+1] for i in range(1,len(split),2)}
                self.assertEqual(set(found),expected_jobs)
                for name,body in found.items():
                    with self.subTest(job=name):
                        self.assertRegex(body,r"(?m)^    if: false\s*$")
                        self.assertIn("    runs-on:",body)
                        self.assertLess(body.index("    if: false"),body.index("    runs-on:"))
                        self.assertIn("FAIL-CLOSED",body)

if __name__=="__main__":
    unittest.main()
