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


if __name__ == "__main__":
    unittest.main()
