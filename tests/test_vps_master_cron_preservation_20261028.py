"""Regression gates for preserving live cron during VPS master activation."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "activate_vps_master_agent.sh"


class CronPreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_backup_never_disables_live_master_cron(self):
        s = self.source
        self.assertNotIn('crontab "$paused"', s)
        self.assertNotIn("MASTER_FACTORY_CRON_PAUSED_FOR_DATABASE_SNAPSHOT", s)
        self.assertIn("MASTER_FACTORY_CRON_PRESERVED_DURING_DATABASE_SNAPSHOT", s)
        self.assertLess(s.index("MASTER_BACKUP_VERIFIED"), s.index('cron_replaced=1\ncrontab "$tmp"'))

    def test_snapshot_is_bounded_and_disk_guarded(self):
        s = self.source
        self.assertIn("MASTER_DB_BACKUP_BOUNDED_DEADLINE", s)
        self.assertIn("MASTER_DB_BACKUP_CONCURRENT_WRITER_RESTART_LIMIT", s)
        self.assertIn("MASTER_DB_BACKUP_DISK_RESERVE", s)
        self.assertIn('backup.execute("PRAGMA integrity_check")', s)

    def test_source_swaps_hold_both_worker_locks(self):
        s = self.source
        lock_start = s.index("MASTER_FACTORY_SOURCE_CHANGE_LOCKS_HELD")
        source_swap = s.index('for module in "${modules[@]}"; do', lock_start)
        lock_release = s.index("flock -u 10", source_swap)
        self.assertLess(lock_start, source_swap)
        self.assertLess(source_swap, lock_release)
        self.assertLess(lock_release, s.index('if "$master/run-evolution.sh"'))

    def test_cron_drift_fails_closed_and_failed_replacement_restores(self):
        s = self.source
        self.assertIn('cmp -s "$old" "$current"', s)
        self.assertIn("MASTER_CRON_CONCURRENT_EDIT_BLOCKED", s)
        self.assertIn("MASTER_CRON_RESTORED_AFTER_FAILED_REPLACEMENT", s)
        self.assertIn('[ "${cron_replaced:-0}" -eq 1 ]', s)


if __name__ == "__main__":
    unittest.main()
