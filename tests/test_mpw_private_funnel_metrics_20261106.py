"""Offline production-boundary checks for private, anonymous funnel metrics."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import importlib.util
import os
import sqlite3
import stat
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / "services/mpw_checkout_funnel.py"
spec = importlib.util.spec_from_file_location("mpw_checkout_funnel_unit", PATH)
metric = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metric)


class Metrics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "data"
        self.settings = SimpleNamespace(MPW_PRIVATE_FUNNEL_COUNTERS_ENABLED=True,
                                        MPW_TRX_PUBLIC_PRODUCT_IDS=(72, 225, 779, 879))
        django = ModuleType("django")
        conf = ModuleType("django.conf")
        conf.settings = self.settings
        self.modules = patch.dict(sys.modules, {"django": django, "django.conf": conf})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.patches = (
            patch.object(metric, "ACCOUNT", "test"),
            patch.object(metric, "DATA_DIR", self.dir),
            patch.object(metric, "DATA_FILE", self.dir / "daily-counts.sqlite3"),
            patch.object(metric.pwd, "getpwuid", return_value=SimpleNamespace(pw_name="test")),
        )
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.request = SimpleNamespace(is_secure=lambda: True,
                                       get_host=lambda: "mojplaywin.com",
                                       META={"HTTP_USER_AGENT": "Mozilla/5.0"})

    def test_private_counts_without_visitor_records(self):
        self.assertTrue(metric.record(self.request, "checkout_view", 779))
        self.assertTrue(metric.record(self.request, "order_start_attempt", 779))
        self.assertTrue(metric.record(self.request, "order_start_accepted", 779))
        self.assertTrue(metric.record(self.request, "order_start_not_invoiced", 779))
        self.assertTrue(metric.record(self.request, "order_start_exception", 779))
        self.assertTrue(metric.record(self.request, "paid_download", 12345))
        report = metric.report()
        self.assertEqual(report["status"], "aggregated")
        self.assertEqual([(item["stage"], item["product_id"], item["events"])
                          for item in report["daily"]],
                         [("checkout_view", 779, 1),
                          ("order_start_accepted", 779, 1),
                          ("order_start_attempt", 779, 1),
                          ("order_start_exception", 779, 1),
                          ("order_start_not_invoiced", 779, 1),
                          ("paid_download", 0, 1)])
        self.assertEqual(stat.S_IMODE(self.dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(metric.DATA_FILE.stat().st_mode), 0o600)
        with sqlite3.connect(metric.DATA_FILE) as db:
            columns = [row[1] for row in db.execute("PRAGMA table_info(daily)")]
        self.assertEqual(columns, ["day_utc", "stage", "product_id", "count"])
        self.assertFalse(report["contains_customer_data"])
        self.assertFalse(report["uniques_available"])

    def test_rejected_events_do_not_mutate_storage(self):
        self.settings.MPW_PRIVATE_FUNNEL_COUNTERS_ENABLED = False
        self.assertFalse(metric.record(self.request, "checkout_view", 779))
        self.settings.MPW_PRIVATE_FUNNEL_COUNTERS_ENABLED = True
        self.assertFalse(metric.record(self.request, "checkout_view", 12))
        self.assertFalse(metric.record(self.request, "unknown", 779))
        self.request.META["HTTP_USER_AGENT"] = "Googlebot"
        self.assertFalse(metric.record(self.request, "checkout_view", 779))
        self.assertFalse(metric.DATA_FILE.exists())
        self.assertEqual(metric.report()["status"], "not_installed")

    def test_concurrent_workers_atomic_count(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(lambda _: metric.record(self.request, "checkout_view", 72), range(30)))
        self.assertEqual(results.count(True), 30)
        self.assertEqual(metric.report()["daily"][0]["events"], 30)

    def test_unsafe_storage_fails_open(self):
        self.dir.mkdir(mode=0o700)
        metric.DATA_FILE.symlink_to(Path(self.tmp.name) / "other")
        self.assertFalse(metric.record(self.request, "checkout_view", 72))
        with self.assertRaises(RuntimeError):
            metric.report()


if __name__ == "__main__":
    unittest.main()
