"""Offline safety regressions for independent VPS market-data collection."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


REPO_SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "mojtrade_vps_capture_guard.py"
SOURCE = REPO_SOURCE if REPO_SOURCE.is_file() else Path(__file__).with_name("mojtrade_vps_capture_guard.py")
spec = importlib.util.spec_from_file_location("mojtrade_vps_capture_guard", SOURCE)
guard = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(SOURCE.parent))
try:
    spec.loader.exec_module(guard)
finally:
    sys.path.pop(0)

NOW = datetime(2026, 11, 7, 13, 7, tzinfo=timezone.utc)
EXCESS = guard.MIN_FREE_BYTES + 4 * 1024 * 1024


class VPSCaptureGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / "private"
        self.folder.mkdir(mode=0o700)
        self.journal = self.folder / "hourly.jsonl"
        self.venue = guard.observer.SOURCE

    def check(self, **changes):
        kwargs = {"source_dir": SOURCE.parent, "now": NOW, "free_bytes": EXCESS,
                  "free_inodes": guard.MIN_FREE_INODES + 20}
        kwargs.update(changes)
        return guard.preflight(self.journal, "BTC-USD", self.venue, **kwargs)

    def test_read_only_preflight_does_not_create_journal_or_lock(self):
        result = self.check()
        self.assertEqual(result["status"], "LOCAL_READINESS_ONLY_NOT_ACTIVATED")
        self.assertFalse(result["journal_exists"])
        self.assertEqual(result["real_orders"], 0)
        self.assertFalse(result["remote_source_authenticity_verified"])
        self.assertEqual(len(result["observed_source_sha256"]), 4)
        self.assertFalse(self.journal.exists())
        self.assertFalse(Path(str(self.journal) + ".lock").exists())

    def test_2gib_plus_headroom_is_mandatory(self):
        with self.assertRaisesRegex(guard.GuardReject, "insufficient_disk"):
            self.check(free_bytes=2 * 1024 ** 3)

    def test_inode_reserve_blocks_before_any_lock_creation(self):
        with self.assertRaisesRegex(guard.GuardReject, "insufficient_free_inodes"):
            self.check(free_inodes=guard.MIN_FREE_INODES - 1)
        self.assertFalse(Path(str(self.journal) + ".lock").exists())

    def test_existing_lock_is_reported_without_modification(self):
        lock = Path(str(self.journal) + ".lock")
        lock.touch(mode=0o600)
        before = lock.stat().st_mtime_ns
        result = self.check()
        self.assertTrue(result["existing_private_lock"])
        self.assertEqual(lock.stat().st_mtime_ns, before)

    def test_existing_unsafe_lock_blocks_read_only_preflight(self):
        lock = Path(str(self.journal) + ".lock")
        lock.touch(mode=0o600)
        lock.chmod(0o644)
        with self.assertRaisesRegex(guard.GuardReject, "existing_lock_permissions"):
            self.check()

    def test_existing_symlink_lock_blocks_read_only_preflight(self):
        lock = Path(str(self.journal) + ".lock")
        lock.symlink_to(self.root / "nowhere")
        with self.assertRaisesRegex(guard.GuardReject, "symlink"):
            self.check()

    def test_existing_hardlinked_lock_blocks_read_only_preflight(self):
        lock = Path(str(self.journal) + ".lock")
        lock.touch(mode=0o600)
        alias = self.folder / "alias.lock"
        alias.hardlink_to(lock)
        with self.assertRaisesRegex(guard.GuardReject, "existing_lock_permissions"):
            self.check()

    def test_disk_rejection_creates_no_lock_even_in_run_mode(self):
        with self.assertRaisesRegex(guard.GuardReject, "insufficient_disk"):
            guard.capture_once(self.journal, "BTC-USD", self.venue,
                               source_dir=SOURCE.parent, now=NOW, free_bytes=0)
        self.assertFalse(Path(str(self.journal) + ".lock").exists())

    def test_insecure_directory_rejected(self):
        self.folder.chmod(0o755)
        with self.assertRaisesRegex(guard.GuardReject, "0700"):
            self.check()

    def test_symlinked_ancestor_directory_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.folder, target_is_directory=True)
        with self.assertRaisesRegex(guard.GuardReject, "symlink"):
            guard.preflight(alias / "hourly.jsonl", "BTC-USD", self.venue,
                            source_dir=SOURCE.parent, now=NOW, free_bytes=EXCESS)

    def test_same_venue_quote_capable_market_only(self):
        with self.assertRaisesRegex(guard.GuardReject, "quoted_venue"):
            guard.preflight(
                self.journal, "BTC-USD", guard.observer.BINANCE_SOURCE,
                source_dir=SOURCE.parent, now=NOW, free_bytes=EXCESS)

    def test_reject_outside_hourly_collection_window(self):
        with self.assertRaisesRegex(guard.GuardReject, "outside_safe"):
            self.check(now=NOW.replace(minute=59), require_capture_window=True)

    def test_existing_journal_mixed_venue_fails_closed(self):
        from mojtrade_forward_bar_capture import latest_capture, append_private
        floor = int(NOW.timestamp()) // 3600 * 3600
        rows = []
        for idx in range(60):
            p = 30_000 + idx
            rows.append([floor - (60 - idx) * 3600, p - 3, p + 3, p, p, 1.0])
        event = latest_capture("BTC-USD", rows, guard.observer.KRAKEN_SOURCE, received_at=NOW)
        append_private(event, self.journal)
        with self.assertRaisesRegex(guard.GuardReject, "mixed_venue"):
            self.check()

    def test_existing_journal_unquoted_fails_closed(self):
        from mojtrade_forward_bar_capture import latest_capture, append_private
        floor = int(NOW.timestamp()) // 3600 * 3600
        rows = []
        for idx in range(60):
            p = 30_000 + idx
            rows.append([floor - (60 - idx) * 3600, p - 3, p + 3, p, p, 1.0])
        event = latest_capture("BTC-USD", rows, self.venue, received_at=NOW)
        append_private(event, self.journal)
        with self.assertRaisesRegex(guard.GuardReject, "same_venue_quote"):
            self.check()

    def test_corrupt_or_insecure_journal_rejected(self):
        self.journal.write_text("not-json\n", encoding="utf-8")
        self.journal.chmod(0o600)
        with self.assertRaisesRegex(guard.GuardReject, "integrity_invalid"):
            self.check()
        self.journal.chmod(0o644)
        with self.assertRaisesRegex(guard.GuardReject, "permissions"):
            self.check()

    def test_unsafe_lock_permissions_fail_before_network(self):
        lock = Path(str(self.journal) + ".lock")
        lock.touch(mode=0o666)
        lock.chmod(0o666)
        with patch.object(guard.capture, "capture_public_once") as captured:
            with self.assertRaisesRegex(guard.GuardReject, "existing_lock_permissions_invalid"):
                guard.capture_once(self.journal, "BTC-USD", self.venue,
                                   source_dir=SOURCE.parent, now=NOW, free_bytes=EXCESS)
            captured.assert_not_called()

    def test_concurrent_same_journal_run_rejected_without_market_fetch(self):
        with guard._singleton(self.journal):
            with patch.object(guard.capture, "capture_public_once") as captured:
                with self.assertRaisesRegex(guard.GuardReject, "capture_already_running"):
                    guard.capture_once(self.journal, "BTC-USD", self.venue,
                                       source_dir=SOURCE.parent, now=NOW, free_bytes=EXCESS)
                captured.assert_not_called()

    def test_missing_same_venue_quote_does_not_touch_journal(self):
        with patch.object(guard.capture, "capture_public_once", return_value={
                "venue_claim": self.venue}) as mocked:
            with self.assertRaisesRegex(guard.GuardReject, "same_venue_fresh_quote"):
                guard.capture_once(self.journal, "BTC-USD", self.venue,
                                   source_dir=SOURCE.parent, now=NOW, free_bytes=EXCESS)
            mocked.assert_called_once()
        self.assertFalse(self.journal.exists())

    def test_one_shot_quoted_offline_fixture_writes_private_evidence_only(self):
        from mojtrade_forward_bar_capture import latest_capture
        floor = int(NOW.timestamp()) // 3600 * 3600
        rows = []
        for idx in range(60):
            p = 30_000 + idx
            rows.append([floor - (60 - idx) * 3600, p - 3, p + 3, p, p, 1.0])
        event = latest_capture("BTC-USD", rows, self.venue, received_at=NOW)
        bid, ask = 30_000.0, 30_001.0
        spread = (ask - bid) / ((ask + bid) / 2) * 10_000
        event["spread_bps"] = spread
        event["quote_receipt"] = {
            "schema": guard.quotes.SCHEMA,
            "symbol": "BTC/USD", "venue_claim": self.venue,
            "quote_received_at_utc": "2026-11-07T13:07:05+00:00",
            "book_source_timestamp_utc": "2026-11-07T13:07:04+00:00",
            "book_sequence": 42,
            "bid": bid, "ask": ask, "spread_bps": spread,
            "venue_authenticity_independently_verified": False,
            "execution": "disabled", "publication": "disabled", "real_orders": 0,
        }
        with patch.object(guard.capture, "capture_public_once", return_value=event):
            result = guard.capture_once(self.journal, "BTC-USD", self.venue,
                                        source_dir=SOURCE.parent, now=NOW, free_bytes=EXCESS)
        self.assertTrue(result["written"])
        self.assertEqual(result["real_orders"], 0)
        self.assertEqual(self.journal.stat().st_mode & 0o777, 0o600)
        followup = self.check()
        self.assertEqual(followup["observations"], 1)

    def test_cli_check_blocked_does_not_write(self):
        result = guard.main(["--symbol", "BTC-USD", "--venue", self.venue,
                             "--private-journal", str(self.journal)])
        # Environment may have spare disk; either outcome must be read-only.
        self.assertIn(result, (0, 2))
        self.assertFalse(self.journal.exists())


class VPSLegacyInstallerBoundaryTests(unittest.TestCase):
    """Regression: no writes or installation before enough capacity is proven."""

    def test_workflow_capacity_check_precedes_first_vps_write(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/mojtrade-vps-observer-activate.yml").read_text()
        self.assertIn("MOJTRADE_PREUPLOAD_CAPACITY_PASS", workflow)
        self.assertIn("free_kib >= 2113536", workflow)
        self.assertIn("free_inodes >= 16", workflow)
        self.assertLess(workflow.index("MOJTRADE_PREUPLOAD_CAPACITY_PASS"),
                        workflow.index('install -d -m 700 "$HOME/factory-runtime/operations/mojtrade"'))
        self.assertLess(workflow.index("MOJTRADE_PREUPLOAD_CAPACITY_PASS"),
                        workflow.index("scp \"${opts[@]}\" scripts/mojtrade_observe_market.py"))
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("\n  push:", workflow)

    def test_legacy_installer_has_matching_second_capacity_gate(self):
        root = Path(__file__).resolve().parents[1]
        installer = (root / "deploy/install_mojtrade_observer_vps.sh").read_text()
        self.assertIn("free_kib >= 2113536", installer)
        self.assertIn("free_inodes >= 16", installer)
        self.assertNotIn("free_mb >= 500", installer)
        self.assertLess(installer.index("MOJTRADE_INSUFFICIENT_FREE_SPACE_2GIB_PLUS_16MIB"),
                        installer.index('install -d -m 700 "$operations" "$private"'))


if __name__ == "__main__":
    unittest.main()
