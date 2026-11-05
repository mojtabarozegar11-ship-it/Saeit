"""Guard against reintroducing the legacy cron/runner double-flock bug."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/vps-single-product-factory-activation.yml"


class LegacySingleProductCronTests(unittest.TestCase):
    def test_cron_uses_runner_single_flock_layer(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('exec 9>"{private}/.single-product-cycle.lock"', source)
        self.assertIn("flock -n 9 || exit 0", source)

        cron_lines = [
            line for line in source.splitlines()
            if "SAEIT_SINGLE_PRODUCT_FACTORY_V1" in line
            and "* * * * *" in line
        ]
        self.assertEqual(len(cron_lines), 1, cron_lines)
        self.assertIn("/usr/bin/timeout 55s $runner", cron_lines[0])
        self.assertNotIn("/usr/bin/flock", cron_lines[0])


if __name__ == "__main__":
    unittest.main()
