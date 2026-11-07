"""No-network, fail-closed tests for the existing MojTrade watch-observer contract."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import mojtrade_observer_boundary as boundary


GENERATED = "2026-11-07T12:30:00+00:00"
CLOSED = "2026-11-07T12:00:00+00:00"
NOW = datetime(2026, 11, 7, 13, 0, tzinfo=timezone.utc)


def fixture():
    signals = []
    for symbol, source in (("BTC/USD", "coinbase-exchange-public-candles"),
                           ("ETH/USD", "kraken-spot-public-ohlc")):
        stamp = f"{symbol.replace('/', '-')}|{CLOSED}|{boundary.OBSERVER_METHOD}|{source}"
        signals.append({
            "id": hashlib.sha256(stamp.encode()).hexdigest()[:24],
            "market": "crypto", "symbol": symbol, "timeframe": "1h",
            "stance": "neutral", "observed_at": CLOSED,
            "method": boundary.OBSERVER_METHOD, "data_source": source,
        })
    return {"schema_version": 1, "source": "mojtrade-vps",
            "generated_at": GENERATED, "expires_at": "2026-11-07T14:00:00+00:00",
            "signals": signals}


class BoundaryTests(unittest.TestCase):
    def test_consistent_payload_is_watch_only_and_never_eligible(self):
        report = boundary.audit_observer(fixture(), now=NOW)
        self.assertEqual(report["state"], "CONSISTENT_WATCH_PAYLOAD_RESEARCH_ONLY")
        self.assertFalse(report["engine_input_eligible"])
        self.assertFalse(report["market_authenticity_verified"])
        self.assertFalse(report["commercial_ready"])
        self.assertEqual(report["real_orders"], 0)
        self.assertEqual(report["public_signals"], 0)
        self.assertIn("per_bar_data_available_at_not_recorded", report["blockers"])
        self.assertEqual(report["claimed_data_sources"]["ETH/USD"],
                         "kraken-spot-public-ohlc")

    def test_hash_is_content_identity_not_venue_proof(self):
        a, b = fixture(), fixture()
        b["signals"][0]["stance"] = "watch_buy"
        self.assertNotEqual(boundary.audit_observer(a, now=NOW)["observer_payload_sha256"],
                            boundary.audit_observer(b, now=NOW)["observer_payload_sha256"])
        self.assertFalse(boundary.audit_observer(b, now=NOW)["market_authenticity_verified"])

    def test_expired_observer_rejected(self):
        payload = fixture()
        with self.assertRaisesRegex(boundary.ObserverReject, "expired"):
            boundary.audit_observer(payload, now=datetime(2026, 11, 7, 14, 0, tzinfo=timezone.utc))

    def test_future_generation_rejected(self):
        with self.assertRaises(boundary.ObserverReject):
            boundary.audit_observer(fixture(), now=datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc))

    def test_expiration_window_rejected(self):
        payload = fixture()
        payload["expires_at"] = "2026-11-07T19:00:00+00:00"
        with self.assertRaises(boundary.ObserverReject):
            boundary.audit_observer(payload, now=NOW)

    def test_strict_symbol_order_rejected(self):
        payload = fixture()
        payload["signals"].reverse()
        with self.assertRaises(boundary.ObserverReject):
            boundary.audit_observer(payload, now=NOW)

    def test_source_claim_not_whitelisted(self):
        payload = fixture()
        payload["signals"][0]["data_source"] = "unknown-provider"
        with self.assertRaises(boundary.ObserverReject):
            boundary.audit_observer(payload, now=NOW)

    def test_tampered_research_id_rejected(self):
        payload = fixture()
        payload["signals"][0]["id"] = "f" * 24
        with self.assertRaisesRegex(boundary.ObserverReject, "id_mismatch"):
            boundary.audit_observer(payload, now=NOW)

    def test_unclosed_or_stale_watch_bar_rejected(self):
        payload = fixture()
        payload["signals"][0]["observed_at"] = "2026-11-07T13:00:00+00:00"
        with self.assertRaises(boundary.ObserverReject):
            boundary.audit_observer(payload, now=NOW)
        payload = fixture()
        payload["signals"][0]["observed_at"] = "2026-11-07T08:00:00+00:00"
        with self.assertRaises(boundary.ObserverReject):
            boundary.audit_observer(payload, now=NOW)

    def test_naive_timezone_rejected(self):
        payload = fixture()
        payload["generated_at"] = "2026-11-07T12:30:00"
        with self.assertRaises(boundary.ObserverReject):
            boundary.audit_observer(payload, now=NOW)

    def test_unexpected_trade_instruction_rejected(self):
        payload = fixture()
        payload["signals"][0]["order"] = {"side": "buy", "size": 1}
        with self.assertRaises(boundary.ObserverReject):
            boundary.audit_observer(payload, now=NOW)

    def test_bad_top_level_schema_rejected(self):
        for malformed in (None, [], {**fixture(), "broker_key": "secret"},
                          {**fixture(), "schema_version": True}):
            with self.subTest(malformed=type(malformed).__name__):
                with self.assertRaises(boundary.ObserverReject):
                    boundary.audit_observer(malformed, now=NOW)

    def test_unsafe_naive_clock_rejected(self):
        with self.assertRaises(boundary.ObserverReject):
            boundary.audit_observer(fixture(), now=datetime(2026, 11, 7, 13))

    def test_private_reader_good_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "observer"
            folder.mkdir(mode=0o700)
            path = folder / "validated-payload.json"
            path.write_text(json.dumps(fixture()))
            path.chmod(0o600)
            self.assertEqual(boundary.read_private_payload(path), fixture())

    def test_private_reader_rejects_world_readable_file(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "observer"
            folder.mkdir(mode=0o700)
            path = folder / "validated-payload.json"
            path.write_text(json.dumps(fixture()))
            path.chmod(0o644)
            with self.assertRaises(boundary.ObserverReject):
                boundary.read_private_payload(path)

    def test_private_reader_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "observer"
            folder.mkdir(mode=0o700)
            source = folder / "private.json"
            source.write_text(json.dumps(fixture()))
            source.chmod(0o600)
            alias = folder / "alias.json"
            alias.symlink_to(source)
            with self.assertRaises(boundary.ObserverReject):
                boundary.read_private_payload(alias)

    def test_private_reader_rejects_hardlink(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "observer"
            folder.mkdir(mode=0o700)
            source = folder / "private.json"
            source.write_text(json.dumps(fixture()))
            source.chmod(0o600)
            os.link(source, folder / "alias.json")
            with self.assertRaises(boundary.ObserverReject):
                boundary.read_private_payload(source)

    def test_main_stays_blocked_on_missing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "observer"
            folder.mkdir(mode=0o700)
            from contextlib import redirect_stdout
            from io import StringIO
            capture = StringIO()
            with redirect_stdout(capture):
                exit_code = boundary.main(["--input", str(folder / "absent.json")])
            self.assertEqual(exit_code, 1)
            report = json.loads(capture.getvalue())
            self.assertEqual(report["state"], "BLOCKED_OBSERVER_EVIDENCE")
            self.assertFalse(report["engine_input_eligible"])
            self.assertEqual(report["real_orders"], 0)


if __name__ == "__main__":
    unittest.main()
