"""Disposable Astra 0049 market bridge tests, not a live factory audit."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "astra_stage45_market_queue_bridge.py"
PILOT = ROOT / "research" / "astra-water-margin-us-primary-market-pilot.json"
NOW = "2026-10-15T13:00:00Z"
spec = importlib.util.spec_from_file_location("market_bridge_test", SCRIPT)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class MarketQueueBridgeTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.market_dir = self.root / "research"
        self.market_dir.mkdir()
        self.packet_path = self.market_dir / "pilot.json"
        self.packet_path.write_bytes(PILOT.read_bytes())
        self.db = self.root / "disposable-0049.sqlite3"
        with sqlite3.connect(self.db) as c:
            c.executescript("""
                CREATE TABLE django_migrations (app TEXT, name TEXT);
                INSERT INTO django_migrations VALUES
                    ('core', '0049_astra_stage45_research_queue');
                CREATE TABLE core_factoryqueueitem (
                    id INTEGER PRIMARY KEY, key TEXT, kind TEXT,
                    status TEXT, priority_score NUMERIC,
                    build_authorized INTEGER, publish_authorized INTEGER,
                    payment_authorized INTEGER,
                    evidence_verified_independently INTEGER);
                CREATE TABLE core_discoverysnapshot (
                    id INTEGER PRIMARY KEY,hypothesis_id INTEGER,url TEXT,
                    content_hash TEXT,retrieved_at TEXT,record TEXT);
                INSERT INTO core_factoryqueueitem VALUES
                    (1,'research:legacy-product:10','discovery','RESEARCH_REQUIRED',NULL,0,0,0,0),
                    (2,'research:legacy-product:11','discovery','RESEARCH_REQUIRED',NULL,0,0,0,0);
            """)
        self.pilot_key = "farm_water_land_margin_audit_v1"
        self.key = "research:legacy-product:10"

    def report(self, bindings=None):
        return bridge.evaluate(self.db, self.market_dir, NOW, bindings)

    def make_bindings(self, bindings):
        path = self.root / "explicit-unverified-bindings.json"
        path.write_text(json.dumps({"bindings": bindings}))
        return path

    def test_unlinked_real_pilot_not_assigned_to_any_legacy_product(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        result = self.report()
        self.assertEqual(result["discovery_topics"], 2)
        self.assertEqual(result["market_packets_examined"], 1)
        self.assertEqual(result["explicit_unverified_packet_links"], 0)
        self.assertEqual(result["unlinked_market_product_keys"], [self.pilot_key])
        self.assertEqual(result["topics_without_market_packets"], 2)
        self.assertFalse(result["publish_authorized"])
        self.assertFalse(result["payment_authorized"])
        self.assertEqual(result["factory_mutations"], 0)
        self.assertEqual(before, hashlib.sha256(self.db.read_bytes()).hexdigest())

    def test_explicit_link_always_provisional_not_factory_authority(self):
        bindings = self.make_bindings([
            {"queue_key": self.key, "product_key": self.pilot_key}
        ])
        before = self.db.read_bytes()
        result = self.report(bindings)
        self.assertEqual(result["explicit_unverified_packet_links"], 1)
        self.assertEqual(result["topics_without_market_packets"], 1)
        self.assertEqual(result["unlinked_market_product_keys"], [])
        row = next(x for x in result["research_queue"] if x["queue_key"] == self.key)
        self.assertEqual(row["market_packet_key"], self.pilot_key)
        self.assertEqual(row["market_reference_urls_listed"], 9)
        self.assertEqual(row["market_competitors_listed"], 4)
        self.assertFalse(row["linkage_independently_verified"])
        self.assertFalse(row["build_authorized"])
        self.assertFalse(row["publish_authorized"])
        self.assertFalse(row["payment_authorized"])
        self.assertEqual(row["independently_attested_market_sources"], 0)
        self.assertEqual(row["validated_real_buyer_interviews"], 0)
        self.assertIsNone(row["commercial_quality_score"])
        self.assertIn("VERIFY_WILLINGNESS_TO_PAY_WITH_REAL_BUYERS",
                      row["next_research_actions"])
        self.assertEqual(before, self.db.read_bytes())

    def test_unknown_queue_identity_cannot_invent_attachment(self):
        mapping = self.make_bindings([
            {"queue_key": "research:legacy-product:999", "product_key": self.pilot_key}
        ])
        with self.assertRaisesRegex(ValueError, "unknown queue"):
            self.report(mapping)

    def test_unknown_product_key_cannot_invent_attachment(self):
        mapping = self.make_bindings([
            {"queue_key": self.key, "product_key": "fabricated_product"}
        ])
        with self.assertRaisesRegex(ValueError, "unknown queue"):
            self.report(mapping)

    def test_duplicate_or_ambiguous_packet_attachment_blocked(self):
        mapping = self.make_bindings([
            {"queue_key": self.key, "product_key": self.pilot_key},
            {"queue_key": "research:legacy-product:11", "product_key": self.pilot_key}
        ])
        with self.assertRaisesRegex(ValueError, "duplicate or ambiguous"):
            self.report(mapping)

    def test_self_promoted_queue_blocks_integration(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE core_factoryqueueitem SET build_authorized=1 WHERE id=1")
        with self.assertRaisesRegex(ValueError, "authorization invariant"):
            self.report()

    def test_packet_extra_sale_flag_is_rejected(self):
        data = json.loads(self.packet_path.read_text())
        data["payment_authorized"] = True
        self.packet_path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "five-field"):
            self.report()

    def test_duplicate_product_keys_in_different_files_rejected(self):
        (self.market_dir / "copy.json").write_bytes(self.packet_path.read_bytes())
        with self.assertRaisesRegex(ValueError, "duplicate market product"):
            self.report()

    def test_symlinked_packet_and_bindings_are_denied(self):
        external = self.root / "copy.json"
        external.write_bytes(self.packet_path.read_bytes())
        self.packet_path.unlink()
        self.packet_path.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            self.report()
        self.packet_path.unlink()
        self.packet_path.write_bytes(PILOT.read_bytes())
        good = self.make_bindings([])
        alias = self.root / "alias.json"
        alias.symlink_to(good)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            self.report(alias)

    def test_cli_private_permissions_and_no_overwrite(self):
        out = self.root / "market-triage.json"
        digest = hashlib.sha256(self.db.read_bytes()).hexdigest()
        p = subprocess.run([
            sys.executable, str(SCRIPT), "--db", str(self.db),
            "--market-dir", str(self.market_dir),
            "--now-utc", NOW, "--output", str(out),
        ], capture_output=True, text=True, timeout=15)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("ASTRA_STAGE45_MARKET_PUBLICATION=false", p.stdout)
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        data = json.loads(out.read_text())
        self.assertEqual(data["market_packets_examined"], 1)
        self.assertEqual(data["network_requests"], 0)
        self.assertEqual(data["site_mutations"], 0)
        self.assertEqual(data["payment_attempts"], 0)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), digest)
        for target in [self.db, self.packet_path]:
            denied = subprocess.run([
                sys.executable, str(SCRIPT), "--db", str(self.db),
                "--market-dir", str(self.market_dir),
                "--now-utc", NOW, "--output", str(target),
            ], capture_output=True, text=True, timeout=15)
            self.assertNotEqual(denied.returncode, 0)


if __name__ == "__main__":
    unittest.main()
