"""Closed-bar CSV ingestion contract; all source bytes in tests are synthetic."""

import csv
import hashlib
import importlib.util
import io
import os
import stat
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "mojtrade_market_csv_ingest.py"
if not SOURCE.is_file():
    SOURCE = Path(__file__).with_name("mojtrade_market_csv_ingest.py")
sys.path.insert(0, str(SOURCE.parent))
spec = importlib.util.spec_from_file_location("mojtrade_market_csv_ingest", SOURCE)
ingest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingest)


def rows(count=120):
    origin = datetime(2026, 9, 1, tzinfo=timezone.utc)
    return [{"bar_open_utc": (origin + timedelta(minutes=n)).isoformat(),
             "available_at_utc": (origin + timedelta(minutes=n + 1, milliseconds=100)).isoformat(),
             "open": str(100 + n / 10), "high": str(101 + n / 10),
             "low": str(99 + n / 10), "close": str(100.2 + n / 10),
             "spread_bps": "2.5"} for n in range(count)]


def csv_bytes(source=None):
    target = io.StringIO(newline="")
    writer = csv.DictWriter(target, fieldnames=ingest.FIELDS)
    writer.writeheader()
    writer.writerows(rows() if source is None else source)
    return target.getvalue().encode()


class MarketCsvIngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.private = Path(self.tmp.name) / "private"
        self.private.mkdir(mode=0o700)
        self.sample = csv_bytes()

    def tearDown(self):
        self.tmp.cleanup()

    def ingest(self, raw=None):
        return ingest.import_csv_bytes(self.sample if raw is None else raw,
                                       symbol="BTC/USD", interval_seconds=60,
                                       claimed_provider="BROKER_NOT_VERIFIED")

    def test_complete_observed_closed_bars_convert_to_foundry_schema(self):
        result = self.ingest()
        self.assertEqual(len(result["dataset"]["bars"]), 120)
        self.assertTrue(result["dataset"]["source_id"].startswith("unverified-csv-"))
        self.assertEqual(result["manifest"]["file_sha256"], hashlib.sha256(self.sample).hexdigest())
        self.assertFalse(result["manifest"]["broker_or_venue_authenticated"])
        self.assertFalse(result["manifest"]["market_order_permission"])
        self.assertEqual(result["dataset"]["bars"][0]["t"], "2026-09-01T00:01:00+00:00")
        self.assertEqual(result["dataset"]["bars"][0]["available_at"],
                         "2026-09-01T00:01:00.100000+00:00")
        self.assertEqual(result, self.ingest())

    def test_data_observed_before_bar_close_rejected(self):
        forged = rows()
        forged[0]["available_at_utc"] = forged[0]["bar_open_utc"]
        with self.assertRaisesRegex(ingest.IngestReject, "bar_observed_before_close"):
            self.ingest(csv_bytes(forged))

    def test_missing_or_duplicate_bar_rejected(self):
        forged = rows()
        del forged[31]
        with self.assertRaisesRegex(ingest.IngestReject, "bar_gap_duplicate"):
            self.ingest(csv_bytes(forged))
        forged = rows()
        forged.insert(31, forged[30].copy())
        with self.assertRaisesRegex(ingest.IngestReject, "bar_gap_duplicate"):
            self.ingest(csv_bytes(forged))

    def test_malformed_or_negative_prices_never_silently_corrected(self):
        forged = rows()
        forged[20]["high"] = "-1"
        with self.assertRaisesRegex(ingest.IngestReject, "foundry_dataset"):
            self.ingest(csv_bytes(forged))
        forged = rows()
        forged[20]["close"] = "NaN"
        with self.assertRaisesRegex(ingest.IngestReject, "foundry_dataset"):
            self.ingest(csv_bytes(forged))

    def test_missing_observed_timestamp_and_naive_time_refused(self):
        with self.assertRaisesRegex(ingest.IngestReject, "csv_header_invalid"):
            self.ingest(self.sample.replace(b"available_at_utc,", b"", 1))
        forged = rows()
        forged[0]["bar_open_utc"] = "2026-09-01T00:00:00"
        with self.assertRaisesRegex(ingest.IngestReject, "explicit_utc_required"):
            self.ingest(csv_bytes(forged))

    def test_provider_claim_cannot_change_unverified_source_status(self):
        a = self.ingest()
        b = ingest.import_csv_bytes(self.sample, symbol="BTC/USD", interval_seconds=60,
                                    claimed_provider="FAMOUS_EXCHANGE")
        self.assertEqual(a["dataset"], b["dataset"])
        self.assertEqual(b["manifest"]["evidence_status"], "UNVERIFIED_LOCAL_EXPORT")
        self.assertFalse(b["manifest"]["broker_or_venue_authenticated"])

    def test_observation_timestamp_regression_fails_closed(self):
        forged = rows()
        forged[12]["available_at_utc"] = forged[11]["available_at_utc"]
        with self.assertRaisesRegex(ingest.IngestReject, "bar_observed_before_close_or_out_of_order"):
            self.ingest(csv_bytes(forged))

    def test_regular_file_ingest_yields_identical_dataset(self):
        path = self.private / "export.csv"
        path.write_bytes(self.sample)
        self.assertEqual(self.ingest(), ingest.ingest_file(
            path, symbol="BTC/USD", interval_seconds=60,
            claimed_provider="BROKER_NOT_VERIFIED"))

    def test_imported_bars_feed_full_offline_shadow_without_claiming_authenticity(self):
        fixture_path = ROOT / "tests" / "test_mojtrade_unified_shadow.py"
        if not fixture_path.is_file():
            fixture_path = Path(__file__).with_name("test_mojtrade_unified_shadow.py")
        spec = importlib.util.spec_from_file_location("import_shadows_fixture", fixture_path)
        shadow_fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(shadow_fixture)
        request, decision = shadow_fixture.packet()
        source = []
        for bar in request["market_bars"]["bars"]:
            source.append({"bar_open_utc": (datetime.fromisoformat(bar["t"]) -
                                             timedelta(seconds=60)).isoformat(),
                           "available_at_utc": bar["available_at"],
                           "open": str(bar["open"]), "high": str(bar["high"]),
                           "low": str(bar["low"]), "close": str(bar["close"]),
                           "spread_bps": str(bar["spread_bps"])})
        imported = self.ingest(csv_bytes(source))
        request["market_bars"] = imported["dataset"]
        result = shadow_fixture.shadow.run_shadow(request, self.private, now=decision)
        self.assertEqual(result["status"], "RESEARCH_EXECUTION_REPLAYED")
        self.assertEqual(result["real_orders"], 0)
        self.assertEqual(result["reconciliation"]["receipt"]["risk_reservation"],
                         "REMAINS_RESERVED")
        self.assertEqual(imported["manifest"]["evidence_status"], "UNVERIFIED_LOCAL_EXPORT")

    def test_output_is_private_exclusive_and_not_overwritten(self):
        data = self.ingest()
        target = self.private / "feed-import.json"
        receipt = ingest.save_private(data, target)
        self.assertEqual(receipt["dataset_sha256"], data["manifest"]["normalized_dataset_sha256"])
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        original = target.read_bytes()
        with self.assertRaises(FileExistsError):
            ingest.save_private(data, target)
        self.assertEqual(original, target.read_bytes())

    def test_symlink_source_and_unsafe_output_directory_rejected(self):
        source = self.private / "real.csv"
        source.write_bytes(self.sample)
        shortcut = self.private / "shortcut.csv"
        shortcut.symlink_to(source)
        with self.assertRaisesRegex(ingest.IngestReject, "regular_file_required"):
            ingest.ingest_file(shortcut, symbol="BTC/USD", interval_seconds=60)
        unsafe = Path(self.tmp.name) / "unsafe"
        unsafe.mkdir(mode=0o755)
        with self.assertRaisesRegex(ingest.IngestReject, "private_directory"):
            ingest.save_private(self.ingest(), unsafe / "feed.json")


if __name__ == "__main__":
    unittest.main()
