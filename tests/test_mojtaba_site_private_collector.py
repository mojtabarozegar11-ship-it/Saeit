"""Single-writer site history handoff must never execute while old Cron exists."""
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase

from core.mojtaba_site_fleet import SiteFleetError
from core.mojtaba_site_private_collector import (
    validate_private_mpw_context, collect_private_mpw_as_canonical_bot
)


class MpwPrivateCollectorCutoverTests(SimpleTestCase):
    def test_current_legacy_marker_blocks_duplicate_writer(self):
        cron = "*/15 * * * * python3 /home/zomorod2/.private_mojplaywin_main_agents/evolution_runtime_20261018/mpw_monitor_collector.py --collect # MPW_MAIN_AGENT_DASHBOARD_COLLECTOR_20261018"
        with self.assertRaisesRegex(SiteFleetError, "STILL_ACTIVE"):
            validate_private_mpw_context(
                username="zomorod2", home=Path("/home/zomorod2"),
                cron_text=cron, private_dir_valid=True,
            )

    def test_unknown_crontab_blocks_migration(self):
        with self.assertRaisesRegex(SiteFleetError, "UNAVAILABLE"):
            validate_private_mpw_context(
                username="zomorod2", home=Path("/home/zomorod2"),
                cron_text=None, private_dir_valid=True,
            )

    def test_wrong_host_or_unsafe_private_dir_blocks(self):
        for params in (
            {"username": "other", "home": Path("/home/zomorod2"), "cron_text": "", "private_dir_valid": True},
            {"username": "zomorod2", "home": Path("/home/vps"), "cron_text": "", "private_dir_valid": True},
            {"username": "zomorod2", "home": Path("/home/zomorod2"), "cron_text": "", "private_dir_valid": False},
        ):
            with self.subTest(params=params), self.assertRaises(SiteFleetError):
                validate_private_mpw_context(**params)

    def test_clean_crontab_allows_preflight_not_retirement(self):
        ctx = validate_private_mpw_context(
            username="zomorod2", home=Path("/home/zomorod2"),
            cron_text="0 * * * * /usr/bin/python3 safe_report.py",
            private_dir_valid=True,
        )
        self.assertTrue(ctx["single_writer_preflight"])
        self.assertNotIn("legacy_files_retired", ctx)

    def test_root_cannot_invoke_site_collector(self):
        with patch("core.mojtaba_site_private_collector.os.geteuid", return_value=0):
            with self.assertRaisesRegex(SiteFleetError, "ROOT_EXECUTION_REFUSED"):
                collect_private_mpw_as_canonical_bot()
