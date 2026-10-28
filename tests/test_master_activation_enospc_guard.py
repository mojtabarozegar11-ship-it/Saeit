"""Offline fail-closed regression for VPS master activation ENOSPC incident.

No production access, crontab changes, or database writes.
"""
from pathlib import Path
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy/activate_vps_master_agent.sh"


class MasterActivationENOSPCGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.trap_function = "restore_all() {" + cls.source.split("restore_all() {", 1)[1].split(
            '\nold="$ops/backups/cron-before-master-$stamp.txt"', 1
        )[0]

    def test_shell_parses(self):
        p = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_django_settings_resolve_from_app_root_before_preflight(self):
        s = self.source
        # Remote shell starts outside the Django checkout; config.settings
        # must resolve before the disk guard can enforce fail-closed policy.
        self.assertLess(s.index('cd "$app"'), s.index('DJANGO_SETTINGS_MODULE=config.settings SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 "$py" -'))
        self.assertLess(s.index('cd "$app"'), s.index('install -d -m 700 "$master"'))

    def test_disk_preflight_before_any_mutating_setup(self):
        s = self.source
        self.assertLess(s.index("MASTER_PREFLIGHT_ENOSPC_BLOCKED"),
                        s.index('install -d -m 700 "$master"'))
        self.assertLess(s.index("MASTER_PREFLIGHT_ENOSPC_BLOCKED"),
                        s.index("MASTER_FACTORY_CRON_PAUSED_FOR_DATABASE_SNAPSHOT"))
        self.assertIn("5 * 1024**3 + snapshot + 128 * 1024**2", s)
        self.assertIn("MASTER_PREFLIGHT_CRON_UNCHANGED", s)

    def simulate_failed_exit(self, changed):
        # Stub crontab and rollback: no host crontab or files are touched.
        sh = (
            "set -euo pipefail\n"
            "cron_paused=1; backup_verified=0; stamp=none; ops=/nonexistent\n"
            "old=/nonexistent/saved-cron\n"
            f"source_apply_started={int(changed)}\n"
            "crontab() { echo CRON_RESTORE_ATTEMPT; }\n"
            "rollback_sources() { echo SOURCE_ROLLBACK_ATTEMPT; }\n"
            + self.trap_function + "\n"
            "trap restore_all EXIT\n"
            "exit 75\n"
        )
        return subprocess.run(["bash", "-c", sh], capture_output=True, text=True)

    def test_backup_failure_restores_cron_before_rollback(self):
        p = self.simulate_failed_exit(changed=False)
        self.assertEqual(p.returncode, 75, p.stderr)
        self.assertIn("CRON_RESTORE_ATTEMPT", p.stdout)
        self.assertIn("MASTER_CRON_RESTORED_AFTER_FAILURE", p.stdout)
        self.assertNotIn("SOURCE_ROLLBACK_ATTEMPT", p.stdout)

    def test_changed_sources_restore_cron_first(self):
        p = self.simulate_failed_exit(changed=True)
        self.assertEqual(p.returncode, 75, p.stderr)
        self.assertLess(p.stdout.index("CRON_RESTORE_ATTEMPT"),
                        p.stdout.index("SOURCE_ROLLBACK_ATTEMPT"))

    def test_no_silent_incomplete_snapshot_deletion(self):
        self.assertIn("MASTER_INCOMPLETE_DB_BACKUP_QUARANTINE_MANUAL_REVIEW", self.trap_function)
        self.assertNotIn('rm -f "$ops/backups/master-before-', self.trap_function)


if __name__ == "__main__":
    unittest.main()
