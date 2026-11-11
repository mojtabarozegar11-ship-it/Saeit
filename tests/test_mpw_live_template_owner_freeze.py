"""Owner policy: legacy template-overwriting workflows stay disabled.

This repository test is read-only. It neither connects to nor modifies
the live cPanel, VPS, storefront, CSS, or templates.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RETIRED_WORKFLOWS = {
    "mpw-complete-product-page-20261107-v2.yml": "deploy",
    "mpw-product-seo-social-metadata-20261107.yml": "deploy",
    "mpw-complete-product-template-repair-20261107.yml": "repair",
}


class LiveSiteTemplateOwnerFreezeTests(unittest.TestCase):
    """Fail closed if the three known host-template writers are reactivated."""

    def test_legacy_template_writers_have_no_push_trigger(self):
        for filename in RETIRED_WORKFLOWS:
            with self.subTest(workflow=filename):
                source = (ROOT / ".github" / "workflows" / filename).read_text(encoding="utf-8")
                self.assertIn("on:\n  workflow_dispatch:\n", source)
                self.assertNotIn("\n  push:\n", source)

    def test_legacy_template_writers_always_skip_their_jobs(self):
        for filename, job_name in RETIRED_WORKFLOWS.items():
            with self.subTest(workflow=filename):
                source = (ROOT / ".github" / "workflows" / filename).read_text(encoding="utf-8")
                guard = "jobs:\n  " + job_name + ":\n    if: ${{ false }}"
                self.assertIn(guard, source)

    def test_freeze_is_documented_in_every_workflow(self):
        for filename in RETIRED_WORKFLOWS:
            with self.subTest(workflow=filename):
                source = (ROOT / ".github" / "workflows" / filename).read_text(encoding="utf-8")
                self.assertIn("OWNER FREEZE", source)


if __name__ == "__main__":
    unittest.main()
