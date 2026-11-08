"""Offline regression tests for the scoped cPanel cron readback."""
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts" / "zomorod_cpanel_cron_evidence_readonly.py"
WORKFLOW = ROOT / ".github" / "workflows" / "zomorod-private-command-dispatch.yml"


class CronEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = runpy.run_path(str(PROBE))
        cls.summarize = cls.module["summarize_cron"]

    def test_present_site_schedule_and_all_robot_markers(self):
        site = "*/10 * * * * php /private/worker.php # zm-site-agents-only-v100"
        robots = [
            "0 * * * * worker # " + marker
            for _, marker in self.module["ROBOT_MARKERS"]
        ]
        out = self.summarize("\n".join([site] + robots))
        self.assertEqual(out["SITE_AGENTS_TEN_MINUTE"], "SCHEDULED_MARKER_PRESENT")
        for name, _ in self.module["ROBOT_MARKERS"]:
            self.assertEqual(out[name], "PRESENT_ONCE")
        self.assertEqual(out["WORKER_EXECUTION_PROVEN"], "NO")
        self.assertEqual(out["PRIVATE_DURABLE_RECEIPT_PROVEN"], "NO")

    def test_comment_only_is_not_active(self):
        out = self.summarize("# */10 * * * * worker # zm-site-agents-only-v100\n")
        self.assertEqual(out["SITE_AGENTS_TEN_MINUTE"], "ABSENT")

    def test_duplicate_marker_is_rejected(self):
        line = "*/10 * * * * worker # zm-site-agents-only-v100"
        self.assertEqual(
            self.summarize(line + "\n" + line)["SITE_AGENTS_TEN_MINUTE"],
            "DUPLICATE",
        )

    def test_wrong_interval_is_not_verified(self):
        self.assertEqual(
            self.summarize("0 * * * * worker # zm-site-agents-only-v100")
            ["SITE_AGENTS_TEN_MINUTE"], "SCHEDULE_MISMATCH",
        )

    def test_oversize_fails_closed(self):
        self.assertEqual(self.summarize("x" * 131073), {"READBACK": "UNVERIFIED"})

    def test_probe_does_not_expose_cron_lines(self):
        secret = "PRIVATE_PASSWORD=sensitive"
        out = self.summarize("1 * * * * worker " + secret)
        self.assertNotIn(secret, repr(out))
        self.assertEqual(out["READBACK"], "OK")

    def test_workflow_owner_readonly_guard_and_pinned_identity(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("if: steps.gate.outputs.operation == 'cpanel_readonly'", source)
        self.assertIn("zomorod_cpanel_cron_evidence_readonly.py", source)
        self.assertIn('case "$COMMAND_HOST" in saeit-cpanel|saeit-cpanel-direct)', source)
        self.assertIn("StrictHostKeyChecking yes", source)
        self.assertIn("github.event.issue.number == 1600", source)

    def test_only_readonly_crontab_invocation(self):
        source = PROBE.read_text(encoding="utf-8")
        self.assertIn('["crontab", "-l"]', source)
        self.assertNotIn('["crontab", "-r"]', source)
        self.assertNotIn('["crontab", "-e"]', source)


if __name__ == "__main__":
    unittest.main()
