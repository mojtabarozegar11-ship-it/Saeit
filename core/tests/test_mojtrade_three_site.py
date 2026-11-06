"""The three public surfaces share one closed-by-default MojTrade signal feed."""

import hashlib
import hmac
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings


def _signed_feed(secret, *, expiry_minutes=15):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    generated = now - timedelta(minutes=1)
    payload = {
        "schema_version": 1,
        "generated_at": generated.isoformat(),
        "expires_at": (now + timedelta(minutes=expiry_minutes)).isoformat(),
        "source": "mojtrade-vps",
        "signals": [{
            "id": "evidence-1", "market": "crypto", "symbol": "BTC/USD",
            "timeframe": "1h", "stance": "neutral",
            "observed_at": generated.isoformat(),
            "method": "validated-price-observation", "data_source": "independent-source-id",
        }],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return {"payload": payload, "signature": hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()}


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
class MojTradeThreeSiteTests(SimpleTestCase):
    def test_unconfigured_feed_is_read_only_and_offline(self):
        with patch.dict(os.environ, {
            "MOJTRADE_PUBLIC_FEED_PATH": "", "MOJTRADE_PUBLIC_FEED_HMAC_KEY": "",
            "MOJTRADE_PUBLICATION_ENABLED": "",
        }):
            response = self.client.get("/api/mojtrade/v1/public/", HTTP_HOST="mojplaywin.com")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "offline")
            self.assertEqual(response.json()["signals"], [])
            self.assertFalse(response.json()["live_trading_enabled"])
            self.assertEqual(response.json()["execution_mode"], "disabled")
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(self.client.post("/api/mojtrade/v1/public/").status_code, 405)

    def test_verified_snapshot_stays_private_without_publication_permission(self):
        secret = "test-secret-only-long-enough-0000001"
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "feed.json"
            file.write_text(json.dumps(_signed_feed(secret)), encoding="utf-8")
            with patch.dict(os.environ, {
                "MOJTRADE_PUBLIC_FEED_PATH": str(file),
                "MOJTRADE_PUBLIC_FEED_HMAC_KEY": secret,
                "MOJTRADE_PUBLICATION_ENABLED": "",
            }):
                response = self.client.get("/api/mojtrade/v1/public/")
                self.assertEqual(response.json()["status"], "verified_private")
                self.assertEqual(response.json()["signals"], [])

    def test_explicitly_enabled_valid_feed_and_scoped_cors(self):
        secret = "test-secret-only-long-enough-0000001"
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "feed.json"
            file.write_text(json.dumps(_signed_feed(secret)), encoding="utf-8")
            with patch.dict(os.environ, {
                "MOJTRADE_PUBLIC_FEED_PATH": str(file),
                "MOJTRADE_PUBLIC_FEED_HMAC_KEY": secret,
                "MOJTRADE_PUBLICATION_ENABLED": "true",
            }):
                response = self.client.get("/api/mojtrade/v1/public/", HTTP_ORIGIN="https://zomorodmelal.ir")
                self.assertEqual(response.json()["status"], "verified")
                self.assertEqual(len(response.json()["signals"]), 1)
                self.assertEqual(response["Access-Control-Allow-Origin"], "https://zomorodmelal.ir")
                evil = self.client.get("/api/mojtrade/v1/public/", HTTP_ORIGIN="https://other.example")
                self.assertNotIn("Access-Control-Allow-Origin", evil)

    def test_tampering_and_expired_snapshot_fail_closed(self):
        secret = "test-secret-only-long-enough-0000001"
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "feed.json"
            envelope = _signed_feed(secret)
            envelope["payload"]["signals"][0]["stance"] = "watch_buy"
            file.write_text(json.dumps(envelope), encoding="utf-8")
            with patch.dict(os.environ, {
                "MOJTRADE_PUBLIC_FEED_PATH": str(file),
                "MOJTRADE_PUBLIC_FEED_HMAC_KEY": secret,
                "MOJTRADE_PUBLICATION_ENABLED": "true",
            }):
                self.assertEqual(self.client.get("/api/mojtrade/v1/public/").json()["signals"], [])
                expired = _signed_feed(secret, expiry_minutes=-2)
                file.write_text(json.dumps(expired), encoding="utf-8")
                self.assertEqual(self.client.get("/api/mojtrade/v1/public/").json()["signals"], [])

    def test_only_three_intended_pages_show_read_only_panel(self):
        pages = [
            ("mojplaywin.com", "/ventures/currency-crypto/"),
            ("zomorodmelal.ir", "/economy/"),
        ]
        for host, url in pages:
            with self.subTest(host=host, url=url):
                response = self.client.get(url, HTTP_HOST=host)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-mojtrade-feed="https://mojplaywin.com/api/mojtrade/v1/public/"')
                self.assertContains(response, "READ-ONLY")
        other = self.client.get("/ventures/agriculture/", HTTP_HOST="mojplaywin.com")
        self.assertNotContains(other, "data-mojtrade-feed")
        zahra = Path(__file__).resolve().parents[2] / "templates" / "zahra" / "index.html"
        self.assertIn('data-mojtrade-feed="https://mojplaywin.com/api/mojtrade/v1/public/"', zahra.read_text(encoding="utf-8"))
