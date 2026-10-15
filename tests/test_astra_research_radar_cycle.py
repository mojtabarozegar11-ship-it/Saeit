"""Astra private research cycle: deterministic, no website/factory mutation."""
from datetime import datetime, timezone, timedelta
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "astra_cycle_qa", ROOT / "scripts/astra_research_radar_cycle.py")
cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycle)
NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
RSS = (b'<rss><channel><item><title>Farm production statistics</title>'
       b'<link>https://www.nass.usda.gov/farm-news</link>'
       b'<pubDate>Wed, 14 Oct 2026 12:00:00 GMT</pubDate>'
       b'</item></channel></rss>')


class AstraResearchPrivateCycleTests(unittest.TestCase):
    def test_daily_record_is_private_and_no_second_new_production(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "radar"
            first = cycle.run_cycle(root, now=NOW, fixture=RSS, source="nass_news")
            self.assertEqual(first["status"], "RECORDED")
            self.assertGreaterEqual(first["topic_count"], 1)
            saved = root / "daily-20261015.json"
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            original = saved.read_bytes()
            second = cycle.run_cycle(root, now=NOW, fixture=b"not xml", source="nass_news")
            self.assertEqual(second["status"], "UNCHANGED")
            self.assertEqual(saved.read_bytes(), original)
            data = json.loads(saved.read_text())
            self.assertEqual(data["cycle_version"], "astra_research_daily_v1")
            self.assertEqual(data["run_date_utc"], "20261015")
            for key in ("factory_mutations", "payments", "publications", "commercial_products_built"):
                self.assertEqual(data[key], 0)
            for topic in data["candidate_hypotheses"]:
                self.assertEqual(topic["status"], "RESEARCH_REQUIRED")
                self.assertIsNone(topic["commercial_quality_score"])

    def test_following_day_new_report_preserves_prior(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "radar"
            a = cycle.run_cycle(root, now=NOW, fixture=RSS, source="nass_news")
            b = cycle.run_cycle(root, now=NOW + timedelta(days=1), fixture=RSS, source="nass_news")
            self.assertEqual((a["status"], b["status"]), ("RECORDED", "RECORDED"))
            self.assertEqual(len(list(root.glob("daily-*.json"))), 2)

    def test_no_network_or_file_for_unavailable_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "radar"
            def offline(name):
                raise OSError("no network")
            result = cycle.run_cycle(root, now=NOW, fetcher=offline)
            self.assertEqual(result["status"], "SOURCES_UNAVAILABLE")
            self.assertFalse(list(root.glob("daily-*.json")))

    def test_one_source_down_creates_transparent_partial_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "radar"
            def half(name):
                if name == "nass_news":
                    return RSS
                raise ValueError("not found")
            r = cycle.run_cycle(root, now=NOW, fetcher=half)
            self.assertEqual(r["status"], "RECORDED")
            self.assertEqual(r["feed_count"], 1)
            self.assertEqual(r["failure_count"], 2)

    def test_foreign_existing_report_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "radar"
            root.mkdir()
            existing = root / "daily-20261015.json"
            existing.write_text("foreign private data")
            with self.assertRaises((ValueError, json.JSONDecodeError)):
                cycle.run_cycle(root, now=NOW, fixture=RSS, source="nass_news")
            self.assertEqual(existing.read_text(), "foreign private data")

    def test_symlink_report_denied_without_following(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "radar"
            root.mkdir()
            outside = Path(temp) / "external.json"
            outside.write_text('{"not":"research"}')
            (root / "daily-20261015.json").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "unsafe existing report"):
                cycle.run_cycle(root, now=NOW, fixture=RSS, source="nass_news")
            self.assertEqual(outside.read_text(), '{"not":"research"}')

    def test_symlink_workspace_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / "actual"
            outside.mkdir()
            root = Path(temp) / "alias"
            root.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "symlink workspace"):
                cycle.run_cycle(root, now=NOW, fixture=RSS, source="nass_news")

    def test_fixture_requires_known_source_and_aware_clock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "radar"
            with self.assertRaisesRegex(ValueError, "unrecognized"):
                cycle.run_cycle(root, now=NOW, fixture=RSS, source="evil")
            with self.assertRaisesRegex(ValueError, "timezone-aware"):
                cycle.run_cycle(root, now=datetime(2026,10,15), fixture=RSS, source="nass_news")

    def test_real_daily_loop_does_not_touch_queue_or_prod(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "private-radar"
            factory = Path(temp) / "active-factory.sqlite3"
            factory.write_bytes(b"original-private-factory")
            cycle.run_cycle(root, now=NOW, fixture=RSS, source="nass_news")
            self.assertEqual(factory.read_bytes(), b"original-private-factory")
            self.assertFalse(list(root.rglob("queue.sqlite3")))
            self.assertFalse(list(root.rglob("payments*")))

if __name__ == "__main__":
    unittest.main()
