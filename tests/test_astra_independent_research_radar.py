"""Offline, no-credentials QA for Astra's public-signal-only research radar."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "astra_independent_research_radar.py"
spec = importlib.util.spec_from_file_location("astra_research_radar_test", SCRIPT)
radar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(radar)
NOW = datetime(2026, 10, 15, tzinfo=timezone.utc)


def rss(*items):
    rows = []
    for title, link, pub in items:
        rows.append("<item><title>" + title + "</title><link>" + link +
                    "</link><pubDate>" + pub + "</pubDate></item>")
    return ("<?xml version='1.0'?><rss version='2.0'><channel>" +
            "".join(rows) + "</channel></rss>").encode()


GOOD = rss(
    ("Irrigation water shortages affect crop production",
     "https://www.nass.usda.gov/Newsroom/shortages",
     "Wed, 14 Oct 2026 12:00:00 GMT"),
    ("Farm machinery input costs and fertilizer prices",
     "https://www.nass.usda.gov/Newsroom/costs",
     "Tue, 13 Oct 2026 12:00:00 GMT"),
)


class ResearchRadarTests(unittest.TestCase):
    def report(self, payload=GOOD):
        return radar.research_report({"nass_news": payload}, NOW)

    def test_discovers_distinct_noncommercial_hypotheses(self):
        result = self.report()
        self.assertGreaterEqual(len(result["candidate_hypotheses"]), 2)
        self.assertGreaterEqual(result["distinct_headline_references"], 2)
        for topic in result["candidate_hypotheses"]:
            self.assertEqual(topic["status"], "RESEARCH_REQUIRED")
            self.assertIsNone(topic["commercial_quality_score"])
            self.assertFalse(topic["buyer_willingness_to_pay_verified"])
            self.assertFalse(topic["product_build_authorized"])
            self.assertFalse(topic["store_publication_authorized"])
            self.assertFalse(topic["payment_authorized"])
            self.assertEqual(topic["independent_publishers_confirmed"], 1)
            self.assertIn("DIRECT_BUYER_RESEARCH_MISSING", topic["blockers"])
        self.assertEqual(result["commercial_products_built"], 0)
        self.assertEqual(result["factory_mutations"], 0)

    def test_repeat_scan_does_not_invent_new_products(self):
        report = self.report()
        self.assertEqual(report, self.report())
        self.assertEqual(report["commercial_products_built"], 0)
        self.assertEqual(report["distinct_headline_references"], 2)

    def test_rejects_offsite_or_non_https_urls_and_old_dates(self):
        payload = rss(
            ("Irrigation water report from other domain",
             "https://evil.example/track", "Wed, 14 Oct 2026 12:00:00 GMT"),
            ("Agricultural input costs older report",
             "https://www.nass.usda.gov/old", "Wed, 01 Jan 2020 12:00:00 GMT"),
            ("Agricultural input costs future report",
             "https://www.nass.usda.gov/future", "Fri, 16 Oct 2026 12:00:00 GMT"),
            ("Agricultural water report cleartext transport",
             "http://www.nass.usda.gov/unsafe", "Wed, 14 Oct 2026 12:00:00 GMT"),
        )
        r = self.report(payload)
        self.assertEqual(r["candidate_hypotheses"], [])
        self.assertEqual(r["distinct_headline_references"], 0)

    def test_one_headline_cannot_fake_independent_publishers(self):
        r = radar.research_report({"nass_news": GOOD, "nass_reports": GOOD}, NOW)
        self.assertEqual(r["distinct_headline_references"], 2)
        self.assertTrue(all(t["independent_publishers_confirmed"] == 1
                            for t in r["candidate_hypotheses"]))

    def test_disallowed_entity_or_bomb_and_non_feed_fail_closed(self):
        for payload in (b'<!DOCTYPE x [<!ENTITY a "attack">]><rss/>',
                        b"<html><body>water irrigation</body></html>",
                        b"NOT XML", b"x" * (radar.MAX_FEED_BYTES + 1)):
            with self.subTest(payload=payload[:40]):
                result = self.report(payload)
                self.assertEqual(result["candidate_hypotheses"], [])
                self.assertIn("nass_news", result["feed_failures"])

    def test_forged_sources_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown feed"):
            radar.research_report({"https://evil.example/rss": GOOD}, NOW)
        with self.assertRaisesRegex(ValueError, "unregistered feed"):
            radar.fetch_feed("https://127.0.0.1/admin")

    def test_no_network_during_offline_scan(self):
        with patch.object(radar, "fetch_feed", side_effect=AssertionError("network forbidden")):
            self.assertGreater(len(self.report()["candidate_hypotheses"]), 0)

    def test_atom_supported_with_fixed_source_hostname(self):
        atom = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Crop data research report</title>
<link href="https://www.nass.usda.gov/reports/crop"/>
<updated>2026-10-14T12:00:00Z</updated></entry></feed>"""
        result = self.report(atom)
        self.assertEqual(result["distinct_headline_references"], 1)

    def test_private_output_is_new_only_and_mode_600(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "review.json"
            radar.write_private_new(target, self.report())
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(target.read_text())["publications"], 0)
            with self.assertRaises(FileExistsError):
                radar.write_private_new(target, self.report())

    def test_cli_offline_runs_without_factory_or_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "sample.xml"
            output = Path(tmp) / "research.json"
            fixture.write_bytes(GOOD)
            p = subprocess.run(
                [sys.executable, str(SCRIPT), "--fixture", str(fixture),
                 "--source", "nass_news", "--output", str(output),
                 "--now-utc", "2026-10-15T00:00:00Z"],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("ASTRA_RADAR_FACTORY_MUTATIONS=0", p.stdout)
            self.assertTrue(output.exists())

    def test_recent_official_newsroom_html_generates_research_only(self):
        html = (b'<html><body><div>10/01/26&nbsp; '
                b'<a href="/Newsroom/2026/crop-data">New crop production data report</a>'
                b'</div></body></html>')
        result = radar.research_report({"nass_newsroom": html}, NOW)
        self.assertEqual(result["distinct_headline_references"], 1)
        self.assertGreaterEqual(len(result["candidate_hypotheses"]), 1)
        self.assertTrue(all(not topic["product_build_authorized"]
                            for topic in result["candidate_hypotheses"]))

    def test_old_or_offsite_newsroom_html_rejected(self):
        html = (b'<html><span>01/01/20 '
                b'<a href="/Newsroom/old">Old production statistics</a></span>'
                b'<span>10/01/26 '
                b'<a href="https://evil.example/data">Current production report</a></span></html>')
        result = radar.research_report({"nass_newsroom": html}, NOW)
        self.assertEqual(result["candidate_hypotheses"], [])

    def test_no_article_means_no_product_not_simulated_demand(self):
        empty = rss(("An unrelated meeting announcement",
                     "https://www.nass.usda.gov/unrelated",
                     "Wed, 14 Oct 2026 12:00:00 GMT"))
        r = self.report(empty)
        self.assertEqual(r["candidate_hypotheses"], [])
        self.assertEqual(r["commercial_products_built"], 0)


if __name__ == "__main__":
    unittest.main()
