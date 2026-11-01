"""Regression: generic cPanel deploy must fail before mutating an unready DB."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "cpanel_deploy.sh"


class SafeOfficeDeployOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = DEPLOY.read_text(encoding="utf-8")
        cls.commands = [
            line.strip()
            for line in cls.script.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def test_shell_fail_closed(self):
        self.assertIn("set -euo pipefail", self.commands)

    def test_no_automatic_migration(self):
        migrations = [line for line in self.commands if re.search(r"manage\.py\s+migrate\b", line)]
        self.assertEqual(migrations, ['"$PYTHON" manage.py migrate --check'])
        self.assertNotIn("--fake", self.script)

    def test_read_only_checks_precede_runtime_cutover(self):
        preflight = self.commands.index('"$PYTHON" manage.py migrate --check')
        readiness = self.commands.index('"$PYTHON" manage.py production_gate')
        collect = self.commands.index('"$PYTHON" manage.py collectstatic --noinput')
        restart = self.commands.index("touch passenger_wsgi.py")
        self.assertLess(preflight, readiness)
        self.assertLess(readiness, collect)
        self.assertLess(collect, restart)

    def test_no_silent_gate_bypass(self):
        self.assertEqual(self.commands.count('"$PYTHON" manage.py production_gate'), 1)
        self.assertNotIn("|| true", self.script)


class PrivateOfficeReleaseWorkflowRegression(unittest.TestCase):
    """The old staff login fallback must never patch live Passenger on merge."""

    def test_legacy_login_patcher_removed(self):
        workflow = (ROOT / ".github/workflows/zomorod-office-login-route-release.yml").read_text(encoding="utf-8")
        self.assertNotIn("\n  release:\n", workflow)
        self.assertNotIn("passenger.touch()", workflow)
        self.assertNotIn("/admin/login/?next=/staff/command-center/", workflow)
        self.assertIn("HOST_OR_DB_MUTATION=none", workflow)

    def test_readonly_diagnostic_targets_exact_head_and_tolerates_stage_race(self):
        diag = (ROOT / ".github/workflows/zomorod-office-500-readonly-diagnostic.yml").read_text(encoding="utf-8")
        stage = (ROOT / ".github/workflows/zomorod-messaging-private-staging.yml").read_text(encoding="utf-8")
        self.assertIn("SOURCE_SHA: ${{ github.event.pull_request.head.sha }}", diag)
        self.assertIn("EXACT_HEAD_PRIVATE_STAGE=missing", diag)
        self.assertIn("EXACT_HEAD_PRIVATE_STAGE=verified", diag)
        self.assertIn('os.environ["COMPANY_MESSAGING_SEND_ENABLED"]="false"', diag)
        self.assertIn('".github/workflows/zomorod-office-500-readonly-diagnostic.yml"', stage)


if __name__ == "__main__":
    unittest.main()
