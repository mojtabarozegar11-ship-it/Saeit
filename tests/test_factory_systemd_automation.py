import os
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]


class FactorySystemdAutomationTests(unittest.TestCase):
    def test_shell_files_are_syntactically_valid(self):
        for path in (
            ROOT / "deploy/install_factory_systemd_automation.sh",
            ROOT / "scripts/factory-runtime-watchdog.sh",
        ):
            result = subprocess.run(["bash", "-n", str(path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_install_requires_explicit_approval_before_mutation(self):
        script = ROOT / "deploy/install_factory_systemd_automation.sh"
        result = subprocess.run(
            ["bash", str(script)],
            env={k: v for k, v in os.environ.items()
                 if k != "SAEIT_FACTORY_SYSTEMD_INSTALL_APPROVED"},
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FACTORY_SYSTEMD_INSTALL_APPROVAL_REQUIRED", result.stderr)

    def test_live_singleton_preflight_runs_before_install(self):
        script = (ROOT / "deploy/install_factory_systemd_automation.sh").read_text()
        start = 'python3 - "$runtime" <<\'PY\'\n'
        self.assertIn(start, script)
        payload = script.split(start, 1)[1].split("\nPY\n", 1)[0]
        compile(payload, "f01-systemd-preflight", "exec")
        self.assertIn("F01_PREFLIGHT_SLOT_NOT_EXACT_FIRST_PRODUCT", payload)
        self.assertIn("F01_PREFLIGHT_GLOBAL_SINGLETON_NOT_PROVEN", payload)
        self.assertIn("factory_global_singleton_v1.py", payload)
        self.assertLess(script.index("F01_PREFLIGHT_GLOBAL_SINGLETON_NOT_PROVEN"),
                        script.index('install -d -m 700 "$runtime"'))

    def test_competing_legacy_cron_is_rejected_before_install(self):
        script = (ROOT / "deploy/install_factory_systemd_automation.sh").read_text()
        self.assertIn("crontab -u githubops -l", script)
        self.assertIn("SAEIT_SINGLE_PRODUCT_FACTORY_V1", script)
        self.assertIn("F01_PREFLIGHT_COMPETING_FACTORY_CRON_PRESENT", script)
        self.assertIn("F01_PREFLIGHT_COMPETING_SYSTEMD_TIMER_PRESENT", script)
        self.assertLess(script.index("F01_PREFLIGHT_COMPETING_FACTORY_CRON_PRESENT"),
                        script.index('install -d -m 700 "$runtime"'))

    def test_existing_native_staging_loop_is_rejected_before_install(self):
        script = (ROOT / "deploy/install_factory_systemd_automation.sh").read_text()
        self.assertIn("pgrep -f", script)
        self.assertIn("vps-only-loop", script)
        self.assertIn("factory_staging_tick", script)
        self.assertIn("F01_PREFLIGHT_COMPETING_STAGING_LOOP_PRESENT", script)
        self.assertIn("F01_PREFLIGHT_PROCESS_INVENTORY_UNREADABLE", script)
        self.assertLess(script.index("F01_PREFLIGHT_COMPETING_STAGING_LOOP_PRESENT"),
                        script.index('install -d -m 700 "$runtime"'))

    def test_units_are_persistent_and_one_product_only(self):
        cycle = (ROOT / "deploy/systemd/saeit-factory-cycle.timer").read_text()
        watchdog = (ROOT / "deploy/systemd/saeit-factory-watchdog.timer").read_text()
        service = (ROOT / "deploy/systemd/saeit-factory-cycle.service").read_text()
        self.assertIn("Persistent=true", cycle)
        self.assertIn("OnUnitActiveSec=1min", cycle)
        self.assertIn("Persistent=true", watchdog)
        self.assertIn("SAEIT_FACTORY_AUTORUN_ENABLED=1", service)

    def test_watchdog_requires_singleton_and_does_not_certify_qc(self):
        watchdog = (ROOT / "scripts/factory-runtime-watchdog.sh").read_text()
        start = 'python3 - "$health" "$slots" "$state" "$lane" <<\'PY\'\n'
        self.assertIn(start, watchdog)
        payload = watchdog.split(start, 1)[1].split("\nPY\n", 1)[0]
        compile(payload, "f01-factory-watchdog", "exec")
        self.assertIn("F01_WATCHDOG_QC_RECEIPT=NOT_ASSESSED", payload)

        with TemporaryDirectory() as temp:
            path = Path(temp)
            data = [
                {"schema": "saeit.factory.production-health.v1",
                 "last_cycle_finished_at_utc": datetime.now(timezone.utc).isoformat()},
                {"schema": "saeit.factory.product-slots.v1", "capacity": 1,
                 "active": [{"recipe": "farm_enterprise_economics"}]},
                {"active_product_slot_capacity": 1,
                 "active_product_slot_recipes": ["farm_enterprise_economics"],
                 "publication_locked_until_owner_approval": True,
                 "commercial_quality_review_completed": False,
                 "publishable_product_count": 0},
                {"schema": "saeit.factory.global-single-production-lane.v1",
                 "owner": "line41", "generation": 1},
            ]
            files = [path / f"state-{i}.json" for i in range(4)]

            def check():
                for p, document in zip(files, data):
                    p.write_text(json.dumps(document), encoding="utf-8")
                return subprocess.run(
                    ["python3", "-", *[str(p) for p in files]],
                    input=payload, capture_output=True, text=True)

            passing = check()
            self.assertEqual(passing.returncode, 0, passing.stderr)
            self.assertIn("F01_WATCHDOG_RUNTIME_HEALTH=PASS", passing.stdout)
            self.assertIn("F01_WATCHDOG_QC_RECEIPT=NOT_ASSESSED", passing.stdout)

            data[1]["active"].append({"recipe": "second_product"})
            self.assertNotEqual(check().returncode, 0)
            data[1]["active"].pop()
            data[3]["owner"] = "unknown"
            self.assertNotEqual(check().returncode, 0)
            data[3]["owner"] = "line41"
            data[2]["publishable_product_count"] = 1
            self.assertNotEqual(check().returncode, 0)
            data[2]["publishable_product_count"] = 0
            data[0]["last_cycle_finished_at_utc"] = (
                datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
            self.assertNotEqual(check().returncode, 0)


if __name__ == "__main__":
    unittest.main()

