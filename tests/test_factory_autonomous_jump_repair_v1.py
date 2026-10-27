"""Regression of the autonomous jump self-repair evidence boundary."""
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

MODULE = Path(__file__).resolve().parents[1] / "scripts/factory_autonomous_jump_repair_v1.py"
spec = importlib.util.spec_from_file_location("factory_jump_repair_test", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class JumpRepairTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.base = self.root / "quality-excellence"
        self.base.mkdir()
        self.registry = self.root / "families.json"
        self.registry.write_text(json.dumps({
            "schema": "saeit.factory.family-registry.v1",
            "profiles": [{"id": "F%02d" % n} for n in range(1, 41)]
        }))
        (self.base / "production-workorders").mkdir()
        self.recipe = "fieldwork_fixture"
        self.candidate_hash = None

    def seed(self, *, original="a" * 64, family="F28", changed=True):
        name = self.recipe
        proof_dir = self.base / "native-rebuild-receipts" / name
        proof_dir.mkdir(parents=True)
        qa_dir = self.base / "rework" / name
        qa_dir.mkdir(parents=True)
        qa = qa_dir / "current.json"
        qa.write_text(json.dumps({"artifact_sha256": original}))
        digest = hashlib.sha256(qa.read_bytes()).hexdigest()
        order_dir = self.base / "production-workorders" / name
        order_dir.mkdir(parents=True)
        (order_dir / "current.json").write_text(json.dumps({
            "schema": "saeit.factory.production-rework-order.v1", "recipe": name,
            "artifact_sha256": original, "source_quality_receipt_sha256": digest}))
        stock = self.root / "digital-products" / name
        stock.mkdir(parents=True)
        (stock / "manufacturing_manifest.json").write_text(
            json.dumps({"family_id": family, "recipe": name}))
        output = self.base / "rebuilt-technical-candidates" / name
        output.mkdir(parents=True)
        archive = output / (name + "-internal-qa.zip")
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr(name + "/README.md", "genuine technical fixture")
        candidate = hashlib.sha256(archive.read_bytes()).hexdigest()
        if not changed:
            original = candidate
            qa.write_text(json.dumps({"artifact_sha256": original}))
            digest = hashlib.sha256(qa.read_bytes()).hexdigest()
            order = order_dir / "current.json"
            payload = json.loads(order.read_text())
            payload.update(artifact_sha256=original,
                           source_quality_receipt_sha256=digest)
            order.write_text(json.dumps(payload))
        (output / "manufacturing_manifest.json").write_text(json.dumps({
            "recipe": name, "source_sha256": "b" * 64,
            "artifact_sha256": candidate, "qa_status": "passed",
            "professional_quality_approved": False,
            "public_listing_enabled": False,
            "owner_publication_approval": False}))
        basis = hashlib.sha256((name + "b" * 64 + digest).encode()).hexdigest()
        proof = proof_dir / ("source-" + basis[:24] + ".json")
        proof.write_text(json.dumps({
            "schema": "saeit.factory.qa-native-rebuild-bridge.v1",
            "recipe": name, "source_order_sha256": digest,
            "source_sha256": "b" * 64, "artifact_sha256": candidate,
            "status": "technical_candidate_verified",
            "independent_quality_1000_passed": False,
            "commercial_release_authorized": False,
            "original_stock_mutated": False}))
        self.candidate_hash = candidate
        return archive

    def test_real_package_is_reverified_without_fake_quality_certification(self):
        self.seed()
        first = m.reinspect(self.root, m.families(self.registry))
        second = m.reinspect(self.root, m.families(self.registry))
        self.assertEqual(first, second)
        self.assertEqual(first["machine_candidates_reverified"], 1)
        self.assertEqual(first["genuinely_changed_candidates"], 1)
        self.assertEqual(first["queued_for_independent_reinspection"], 1)
        self.assertEqual(first["family_ids_with_verified_candidates"], ["F28"])
        receipt_dir = self.base / "autonomous-repair-verifications" / self.recipe
        files = list(receipt_dir.glob("candidate-*.json"))
        self.assertEqual(len(files), 1)
        record = json.loads(files[0].read_text())
        self.assertEqual(files[0].name, "candidate-" +
                         hashlib.sha256(files[0].read_bytes()).hexdigest() + ".json")
        self.assertTrue(record["zip_member_crc_verified"])
        for field in ("commercial_release_allowed", "owner_signature_claimed",
                      "professional_quality_1000_certified", "quality_defect_closed"):
            self.assertIs(record[field], False)

    def test_tampered_archive_never_creates_authoritative_receipt(self):
        archive = self.seed()
        archive.write_bytes(archive.read_bytes() + b"tampered")
        r = m.reinspect(self.root, m.families(self.registry))
        self.assertEqual(r["invalid_candidate_receipts"], 1)
        self.assertEqual(r["queued_for_independent_reinspection"], 0)
        self.assertFalse((self.base / "autonomous-repair-verifications").exists())

    def test_same_artifact_cannot_claim_corrected_version(self):
        self.seed(changed=False)
        r = m.reinspect(self.root, m.families(self.registry))
        self.assertEqual(r["machine_candidates_reverified"], 1)
        self.assertEqual(r["genuinely_changed_candidates"], 0)
        self.assertEqual(r["queued_for_independent_reinspection"], 0)

    def test_unknown_family_must_not_enter_independent_reinspection_queue(self):
        self.seed(family="F99")
        r = m.reinspect(self.root, m.families(self.registry))
        self.assertEqual(r["family_provenance_pending"], 1)
        self.assertEqual(r["queued_for_independent_reinspection"], 0)

    def test_obsolete_workorder_is_ignored_without_reapproval(self):
        self.seed()
        order = self.base / "production-workorders" / self.recipe / "current.json"
        doc = json.loads(order.read_text())
        doc["source_quality_receipt_sha256"] = "c" * 64
        order.write_text(json.dumps(doc))
        r = m.reinspect(self.root, m.families(self.registry))
        self.assertEqual(r["machine_candidates_reverified"], 0)

    def test_unsafe_zip_member_blocks_candidate(self):
        archive = self.seed()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("../escape", "attack")
        output = self.base / "rebuilt-technical-candidates" / self.recipe
        candidate = hashlib.sha256(archive.read_bytes()).hexdigest()
        doc_path = output / "manufacturing_manifest.json"
        doc = json.loads(doc_path.read_text())
        doc["artifact_sha256"] = candidate
        doc_path.write_text(json.dumps(doc))
        proof = next((self.base / "native-rebuild-receipts" / self.recipe).glob("source-*.json"))
        record = json.loads(proof.read_text())
        record["artifact_sha256"] = candidate
        proof.write_text(json.dumps(record))
        self.assertEqual(m.reinspect(self.root, m.families(self.registry))
                         ["invalid_candidate_receipts"], 1)

    def test_bounded_execution_runs_twice_only_and_never_releases(self):
        class Bridge:
            count = 0

            @classmethod
            def execute(cls, *args, **kwargs):
                cls.count += 1
                self.assertEqual(kwargs["limit"], 3)
                return {"rebuild_attempted": 3, "technical_candidates_verified": 1,
                        "failed": 0, "professional_quality_1000_verified": False,
                        "commercial_release_authorized": False}
        with patch.object(m, "load_bridge", return_value=Bridge):
            result = m.run(self.root, self.registry, self.root,
                           MODULE, MODULE, rounds=2, limit=3)
        self.assertEqual(Bridge.count, 2)
        self.assertEqual(result["rebuild_attempted"], 6)
        self.assertEqual(result["registered_family_lines"], 40)
        self.assertEqual(result["publications_authorized"], 0)

    def test_lock_conflicts_are_not_ignored(self):
        path = self.base / ".autonomous-jump-repair.lock"
        with path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            class Bridge:
                @staticmethod
                def execute(*args, **kwargs):
                    raise AssertionError("should never run with lock held")
            with patch.object(m, "load_bridge", return_value=Bridge):
                with self.assertRaisesRegex(RuntimeError, "ALREADY_RUNNING"):
                    m.run(self.root, self.registry, self.root, MODULE, MODULE)


    def test_active_allowlist_accepts_single_line_and_legacy_five_slots(self):
        slots = self.root / "active-slots.json"
        for capacity in (1, 5):
            recipes = ["product_line_%02d" % n for n in range(1, capacity + 1)]
            slots.write_text(json.dumps({
                "schema": "saeit.factory.product-slots.v1",
                "capacity": capacity,
                "active": [{"recipe": recipe} for recipe in recipes],
            }))
            self.assertEqual(m.active_product_allowlist(slots), set(recipes))

    def test_active_allowlist_rejects_family_count_as_line_capacity(self):
        slots = self.root / "active-slots.json"
        slots.write_text(json.dumps({
            "schema": "saeit.factory.product-slots.v1",
            "capacity": 40,
            "active": [{"recipe": "product_line_%02d" % n} for n in range(1, 41)],
        }))
        with self.assertRaisesRegex(ValueError, "CAPACITY_MISMATCH"):
            m.active_product_allowlist(slots)

if __name__ == "__main__":
    unittest.main()
