"""Read-only source-of-truth tests, confined to temporary MojPlayWin fixtures."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from scripts.mpw_p0_runtime_identity_readonly_20261019 import inspect_runtime, MARKERS


class MojPlayWinRuntimeProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "mojplaywin.com"
        self.app = base / "saeit"
        self.private = base / ".private_mojplaywin_main_agents"
        for d in (self.root, self.app, self.private):
            d.mkdir()
        (self.root / "passenger_wsgi.py").write_text("APP='" + str(self.app) + "'\n")
        (self.root / ".htaccess").write_text("PassengerAppRoot " + str(self.root))
        self.cron = "\n".join("* * * * * /bin/true # " + marker
                              for marker in MARKERS.values())
        self.now = datetime(2026, 10, 19, 8, tzinfo=timezone.utc)

    def inspect(self):
        return inspect_runtime(root=self.root, app=self.app, private=self.private,
                               cron_text=self.cron, now=self.now)

    def test_pinned_identity_and_tenant_only(self):
        result = self.inspect()
        self.assertTrue(result["runtime_identity_verified"])
        self.assertEqual(result["domain"], "mojplaywin.com")
        self.assertEqual(result["tenant"], "mojplaywin-main")
        self.assertTrue(result["cron_markers_unique"])
        self.assertFalse(result["module_functional_execution_verified"])
        self.assertFalse(result["other_sites_examined"])
        self.assertEqual(result["site_writes"], 0)

    def test_passenger_mismatch_never_claims_authority(self):
        (self.root / "passenger_wsgi.py").write_text("APP='/other/site'")
        result = self.inspect()
        self.assertFalse(result["runtime_identity_verified"])
        self.assertEqual(result["runtime_identity"], "unverified")

    def test_module_imports_are_not_functional_proof(self):
        evo = self.private / "evolution_runtime_20261018"
        evo.mkdir()
        report = {"tenant": "mojplaywin-main", "observed_utc": self.now.isoformat(),
                  "per_module_capability_registry": [
                      {"module": "m" + str(i), "loaded": True} for i in range(77)]}
        (evo / "all_77_modules_last_run.json").write_text(json.dumps(report))
        result = self.inspect()
        self.assertEqual(result["module_import_count"], 77)
        self.assertFalse(result["module_functional_execution_verified"])
        self.assertEqual(result["module_report_age_seconds"], 0)

    def test_missing_invalid_cron_and_symlink_fail_closed(self):
        self.cron = "0 0 * * * /bin/true # unrelated"
        self.assertFalse(self.inspect()["cron_markers_unique"])
        (self.root / "passenger_wsgi.py").unlink()
        (self.root / "passenger_wsgi.py").symlink_to(self.root / ".htaccess")
        self.assertFalse(self.inspect()["runtime_identity_verified"])


if __name__ == "__main__":
    unittest.main()
