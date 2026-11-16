"""No-write inventory against isolated temporary, fake cPanel tree."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mojtaba_site_legacy_cpanel_inventory.py"
spec = importlib.util.spec_from_file_location("site_legacy_inventory", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CPanelInventoryTests(unittest.TestCase):
    def test_only_four_pinned_files_and_two_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            for paths in m.FILES.values():
                for relative in paths:
                    p = home / relative
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text("real code fixture " * 9, encoding="utf-8")
            # Financial/customer data must never even be opened.
            secret = home / ".private/zomorod-business" / "site_agents.sqlite3"
            secret.write_text("KEEP UNTOUCHED")
            cron = (
                "*/10 * * * * /usr/bin/php /x/site_agent_cycle_cli.php # zm-site-agents-only-v100\n"
                "*/15 * * * * /usr/bin/python3 /y/mpw_monitor_collector.py # MPW_MAIN_AGENT_DASHBOARD_COLLECTOR_20261018\n"
                "0 * * * * /path/to/payment_worker --secret=private\n"
            )
            result = m.scan(home, cron_text=cron)
            self.assertEqual(result["canonical_bot"], "mojtaba.bot.ai")
            self.assertFalse(result["safe_to_delete"])
            self.assertFalse(result["crontab_modified"])
            self.assertEqual(len(result["files"]["zomorodmelal"]), 3)
            self.assertEqual(len(result["files"]["mojplaywin"]), 1)
            self.assertEqual(result["cron"]["zomorodmelal"]["matching_count"], 1)
            self.assertEqual(result["cron"]["mojplaywin"]["matching_count"], 1)
            self.assertEqual(secret.read_text(), "KEEP UNTOUCHED")
            self.assertNotIn("payment_worker", str(result))
            self.assertNotIn("--secret", str(result))
            self.assertEqual(result["candidate_bytes_not_confirmed_reclaimable"], 4*len("real code fixture "*9))

    def test_symlink_target_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            parent = home / ".private/zomorod-business"
            parent.mkdir(parents=True)
            target = home / "protected.bin"
            target.write_text("should never read")
            (parent / "site_agents.php").symlink_to(target)
            data = m.scan(home, cron_text="")
            self.assertEqual(data["files"]["zomorodmelal"][0]["state"], "symlink_or_not_regular")
            self.assertEqual(target.read_text(), "should never read")

    def test_missing_cron_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = m.scan(Path(tmp), cron_text=None)
            self.assertIsNone(result["cron"]["mojplaywin"]["matching_count"])
            self.assertEqual(result["cron"]["zomorodmelal"]["state"], "unavailable")

    def test_duplicate_crons_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = m.scan(Path(tmp), cron_text="* * * * * x # zm-site-agents-only-v100\n"*2)
            self.assertTrue(result["cron"]["zomorodmelal"]["duplicate_marker"])
            self.assertEqual(result["cron"]["zomorodmelal"]["matching_count"], 2)

    def test_arbitrary_root_or_parent_symlink_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/"realdir").mkdir()
            (root/"symlink").symlink_to(root/"realdir", target_is_directory=True)
            with self.assertRaises(ValueError):
                m.scan(root/"symlink", cron_text="")
            (root/".private").symlink_to(root/"realdir", target_is_directory=True)
            row = m.scan(root, cron_text="")["files"]["zomorodmelal"][0]
            self.assertEqual(row["state"], "unavailable_or_unsafe_parent")
