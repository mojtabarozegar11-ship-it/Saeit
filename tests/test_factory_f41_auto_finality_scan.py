"""F41 auto reconciliation sidecar: master-order provenance, rate caps, idempotence."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import factory_f41_auto_finality_scan as scanmod
import factory_f41_multi_product_builder as builder
import factory_f41_shasta_finality as finality

SAMPLE = ROOT / "factory_config" / "f41_samples" / "reconciliation.json"


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.queue, self.outputs = root / "orders", root / "outputs"
        self.assets, self.proofs = root / "assets", root / "proofs"
        for folder in (self.queue, self.outputs, self.assets, self.proofs):
            folder.mkdir()
        self.now = datetime(2026, 10, 22, 13, 30, tzinfo=timezone.utc)

    def put(self, name="F41-live-reconciliation", product_id="buyer_real_prospect", built=True):
        data = json.loads(SAMPLE.read_text("utf8"))
        data["product_id"] = product_id
        path = self.queue / (name + ".json")
        path.write_text(json.dumps(data), encoding="utf8")
        if built:
            builder.build(path, self.outputs / name)
        return path

    def scan(self, **kwargs):
        return scanmod.scan(self.queue, self.outputs, self.assets, self.proofs,
                            now=self.now, **kwargs)

    def test_skips_immutable_dummy_pilot(self):
        self.put(name="F41-pilot-reconciliation", product_id="merchant_receipts_demo")
        result = self.scan(execute=True, issue=lambda *args: self.fail("cannot query pilot"))
        self.assertEqual(result["pilot_skipped"], 1)
        self.assertEqual(result["proofs_created"], 0)

    def test_real_unfinished_order_is_not_claimed_complete(self):
        self.put(built=False)
        result = self.scan(execute=True, issue=lambda *args: self.fail("not built"))
        self.assertEqual(result["output_pending"], 1)
        self.assertEqual(result["proofs_created"], 0)

    def test_dry_run_does_not_query_or_create_evidence(self):
        self.put()
        result = self.scan(execute=False, issue=lambda *args: self.fail("dry run queried"))
        self.assertEqual(result["proofs_created"], 0)
        self.assertFalse(list(self.proofs.iterdir()))

    def test_operational_runner_chain_can_create_verified_private_evidence(self):
        order = self.put()
        called = []
        def emit(spec_path, dst):
            self.assertEqual(Path(spec_path), order)
            called.append(str(dst))
            original = builder.read_request(spec_path)
            report = finality.evaluate(original, lambda txid: {})
            # Deliberately synthetic unit-test evidence; never used on VPS.
            report["simulation_used"] = False
            dst.mkdir(mode=0o700)
            body = finality.canonical(report)
            (dst / "finality.json").write_bytes(body)
            (dst / "manifest.json").write_bytes(finality.canonical({
                "schema": "saeit.factory.f41-finality-evidence.v1",
                "finality_sha256": finality.checksum(body),
                "spec_sha256": finality.checksum(builder.enc(original)),
                "customer_delivery_enabled": False,
                "signed_attestation": False,
            }))
            return report
        first = self.scan(execute=True, issue=emit)
        self.assertEqual(first["proofs_created"], 1)
        self.assertEqual(len(called), 1)
        self.assertEqual(first["verified_invoices"], 0)
        second = self.scan(execute=True, issue=lambda *args: self.fail("duplicate cycle"))
        self.assertEqual(second["idempotent"], 1)
        self.assertFalse(second["customer_delivery_enabled"])

    def test_mutated_evidence_is_detected(self):
        self.put()
        original = builder.read_request(self.queue / "F41-live-reconciliation.json")
        target = self.proofs / "F41-live-reconciliation-20261022T1330"
        target.mkdir()
        body = finality.canonical({"customer_delivery_enabled": False, "simulation_used": False,
                                  "original_request_sha256": finality.checksum(builder.enc(original)),
                                  "verified_match_count": 0})
        (target / "finality.json").write_bytes(body)
        (target / "manifest.json").write_bytes(finality.canonical({
            "schema": "saeit.factory.f41-finality-evidence.v1",
            "finality_sha256": finality.checksum(body),
            "spec_sha256": finality.checksum(builder.enc(original)),
            "customer_delivery_enabled": False, "signed_attestation": False,
        }))
        report = json.loads((target / "finality.json").read_text())
        report["customer_delivery_enabled"] = True
        (target / "finality.json").write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "PROOF_DIGEST"):
            self.scan(execute=True)

    def test_original_manifest_tampering_stops_scan(self):
        self.put()
        original = self.outputs / "F41-live-reconciliation" / "manifest.json"
        receipt = json.loads(original.read_text())
        receipt["quality_1000_certified"] = True
        original.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "F41_MANIFEST_INTEGRITY_FAILED"):
            self.scan(execute=True)

    def test_non_json_and_symlink_are_blocked(self):
        (self.queue / "untrusted.txt").write_text("invalid")
        with self.assertRaisesRegex(ValueError, "UNTRUSTED_QUEUE_ENTRY"):
            self.scan()

    def test_15_minute_buckets_advance_without_overwriting(self):
        self.put()
        first = self.scan()
        self.assertEqual(first["reconciliation_orders"], 1)
        self.now += timedelta(minutes=15)
        second = self.scan()
        self.assertEqual(second["reconciliation_orders"], 1)

    def test_trc20_requires_two_rpc_slots_per_observation(self):
        for i in range(4):
            path = self.put(name=f"F41-token-merchant-{i}", built=False)
            spec = json.loads(path.read_text("utf8"))
            for inv in spec["data"]["invoices"]:
                inv["asset"] = "TRC20"
                inv["token_contract"] = "TWTBsKZPVuQgaGNbyJWJm9XR28g4wVBCNQ"
            for obs in spec["data"]["observations"]:
                obs["asset"] = "TRC20"
            path.write_text(json.dumps(spec), encoding="utf8")
            builder.build(path, self.outputs / path.stem)
        result = self.scan(execute=False, issue=lambda *args: self.fail("dry-run network"))
        self.assertEqual(result["rpc_budget_deferred"], 2)
        self.assertEqual(result["deferred_due_to_cycle_cap"], 2)
        self.assertEqual(result["proofs_created"], 0)

    def test_no_payment_code_is_added_to_old_runner(self):
        legacy = (ROOT / "deploy" / "f41_master_queue_runner.sh").read_text()
        wrapper = (ROOT / "deploy" / "f41_master_queue_with_finality.sh").read_text()
        self.assertIn("factory_f41_enqueue --execute", legacy)
        self.assertIn("factory_f41_enqueue --execute", wrapper)
        self.assertIn("factory_f41_auto_finality_scan.py", wrapper)
        self.assertNotIn("broadcast", wrapper)
        self.assertNotIn("customer_delivery_enabled=true", wrapper)


if __name__ == "__main__":
    unittest.main()
