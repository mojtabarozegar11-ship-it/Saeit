"""QC-only regression: test-signed receipts are synthetic *test fixtures*, never products."""
import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

SRC = Path(__file__).resolve().parents[1] / "scripts/factory_real_qc1000_live_monitor_20261023.py"
spec = importlib.util.spec_from_file_location("real_qc1000", SRC)
qc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qc)


def h(raw):
    return hashlib.sha256(raw).hexdigest()


class RealQC1000Tests(unittest.TestCase):
    def setup_factory(self, base, number=1):
        root = Path(base) / "private"
        area = root / "production-instructions"
        receipts = area / "stage-05/downloadable-receipts"
        receipts.mkdir(parents=True)
        (area / "stage-06").mkdir(parents=True)
        for i in range(1, number + 1):
            name = "WO-%08d--r001.json" % i
            archive = area / "stage-05/archives" / (name + ".zip")
            archive.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("README.md", "real data structure check, NOT a certified product")
            receipt = {
                "zip_sha256": h(archive.read_bytes()),
                "archive_relative_path": "stage-05/archives/" + archive.name,
                "ready_for_paid_store": False,
                "scientific_quality_certified": False,
                "public_distribution_allowed": False,
            }
            (receipts / name).write_text(json.dumps(receipt), encoding="utf-8")
        return root, area

    def make_test_signed_suite(self, base, area):
        # These are artificial data used solely to exercise the verifier.
        # They are NOT evidence of independent product testing.
        receipt = json.loads((area / "stage-05/downloadable-receipts/WO-00000001--r001.json").read_text())
        artifact_hash = receipt["zip_sha256"]
        folder = area / "stage-06/real-qc1000-executions/WO-00000001--r001" / artifact_hash
        evidence_dir = folder / "evidence"
        evidence_dir.mkdir(parents=True)
        cases = []
        for i in range(1000):
            cid = "fixture-execution-%04d" % i
            group = "Q%03d" % (i // 10 + 1)
            scenario = h(("unique-test-fixture-" + str(i)).encode())
            event = {
                "schema": qc.CASE_SCHEMA, "scenario_id": cid,
                "criterion_id": group, "scenario_spec_sha256": scenario,
                "artifact_sha256": artifact_hash, "execution_mode": "real_executed_test",
                "status": "PASSED", "exit_code": 0,
                "input_sha256": h(("input-" + str(i)).encode()),
                "expected_sha256": h(("expected-" + str(i)).encode()),
                "observed_sha256": h(("observed-" + str(i)).encode()),
                "test_program_sha256": h(("program-" + str(i)).encode()),
                "started_utc": "2026-10-23T10:00:00Z",
                "finished_utc": "2026-10-23T10:00:01Z",
            }
            raw = qc.canonical(event)
            relative = "evidence/" + cid + ".json"
            (evidence_dir / (cid + ".json")).write_bytes(raw)
            cases.append({
                "scenario_id": cid, "criterion_id": group,
                "scenario_spec_sha256": scenario,
                "execution_receipt_path": relative,
                "execution_receipt_sha256": h(raw),
                "result": "PASSED",
            })
        pub = Path(base) / "test-runner.pub"
        priv = Path(base) / "test-runner.key"
        subprocess.run(["openssl", "genpkey", "-algorithm", "ED25519",
                        "-out", str(priv)], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(priv), "-pubout",
                        "-out", str(pub)], check=True, capture_output=True)
        suite = {
            "schema": qc.SUITE_SCHEMA, "artifact_sha256": artifact_hash,
            "runner_id": "EPHEMERAL_TEST_FIXTURE_NOT_PRODUCTION", "cases": cases
        }
        self.sign_suite(suite, priv, folder)
        return folder / "suite.json", pub, priv

    def sign_suite(self, suite, private, folder):
        signed = {k: v for k, v in suite.items() if k != "signature_hex"}
        payload = folder / "payload.tmp"
        sigfile = folder / "sig.tmp"
        payload.write_bytes(hashlib.sha256(
            b"SAEIT_REAL_QC1000_ED25519_V1\x00" + qc.canonical(signed)
        ).digest())
        subprocess.run(["openssl", "pkeyutl", "-sign", "-rawin",
                        "-inkey", str(private), "-in", str(payload),
                        "-out", str(sigfile)], check=True, capture_output=True)
        suite["signature_hex"] = sigfile.read_bytes().hex()
        (folder / "suite.json").write_bytes(qc.canonical(suite))
        payload.unlink()
        sigfile.unlink()

    def test_health_tick_without_real_1000_never_certifies(self):
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.setup_factory(temp)
            result = qc.scan(root, Path(temp) / "not-enrolled.pub")
            self.assertEqual(result["scanner_health"], "RUNNING")
            self.assertEqual(result["indexed_candidates"], 1)
            self.assertEqual(result["professional_quality_1000_certifications_created"], 0)
            self.assertIn("BLOCKED_NO_REAL1000_EXECUTION_SUITE", result["verdict_counts"])
            self.assertFalse(result["public_sites_modified"])

    def test_bad_original_archive_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root, area = self.setup_factory(temp)
            path = area / "stage-05/archives/WO-00000001--r001.json.zip"
            path.write_bytes(path.read_bytes() + b"TAMPER")
            report = qc.scan(root, Path(temp) / "unused.pub")
            self.assertIn("BLOCKED_ARTIFACT_HASH_MISMATCH", report["verdict_counts"])

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL needed for ephemeral test signatures")
    def test_exact_1000_ten_per_group_signed_receipt_integrity(self):
        with tempfile.TemporaryDirectory() as temp:
            root, area = self.setup_factory(temp)
            suite_path, pub, _ = self.make_test_signed_suite(temp, area)
            artifact = json.loads((area / "stage-05/downloadable-receipts/WO-00000001--r001.json").read_text())["zip_sha256"]
            result = qc.verify_real_suite(suite_path, artifact, pub)
            self.assertEqual(result["verified_distinct_scenarios"], 1000)
            self.assertFalse(result["professionally_quality_certified"])
            cycle = qc.scan(root, pub)
            self.assertEqual(cycle["actual_execution_scenarios_evidence_verified_this_tick"], 1000)
            self.assertEqual(cycle["professional_quality_1000_certifications_created"], 0)

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL needed for ephemeral test signatures")
    def test_duplicate_spec_never_counts_twice(self):
        with tempfile.TemporaryDirectory() as temp:
            _, area = self.setup_factory(temp)
            path, pub, private = self.make_test_signed_suite(temp, area)
            suite = json.loads(path.read_text())
            suite["cases"][1]["scenario_spec_sha256"] = suite["cases"][0]["scenario_spec_sha256"]
            self.sign_suite(suite, private, path.parent)
            with self.assertRaisesRegex(qc.QCFault, "DUPLICATE_SCENARIO_DEFINITION"):
                qc.verify_real_suite(path, suite["artifact_sha256"], pub)

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL needed for ephemeral test signatures")
    def test_tampered_execution_receipt_fails_even_with_signed_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            _, area = self.setup_factory(temp)
            path, pub, _ = self.make_test_signed_suite(temp, area)
            suite = json.loads(path.read_text())
            leaf = path.parent / suite["cases"][0]["execution_receipt_path"]
            leaf.write_bytes(leaf.read_bytes() + b"tamper")
            with self.assertRaisesRegex(qc.QCFault, "CASE_EVIDENCE_HASH_MISMATCH"):
                qc.verify_real_suite(path, suite["artifact_sha256"], pub)

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL needed for ephemeral test signatures")
    def test_untrusted_runner_cannot_sign_quality(self):
        with tempfile.TemporaryDirectory() as temp:
            _, area = self.setup_factory(temp)
            path, _, _ = self.make_test_signed_suite(temp, area)
            other = Path(temp) / "other.key"
            otherpub = Path(temp) / "other.pub"
            subprocess.run(["openssl", "genpkey", "-algorithm", "ED25519",
                            "-out", str(other)], check=True, capture_output=True)
            subprocess.run(["openssl", "pkey", "-in", str(other),
                            "-pubout", "-out", str(otherpub)], check=True, capture_output=True)
            suite = json.loads(path.read_text())
            with self.assertRaisesRegex(qc.QCFault, "UNTRUSTED_RUNNER_SIGNATURE"):
                qc.verify_real_suite(path, suite["artifact_sha256"], otherpub)

    def test_round_robin_does_not_starve_last_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            root, _ = self.setup_factory(temp, 5)
            first = qc.scan(root, Path(temp) / "unused", limit=2)
            second = qc.scan(root, Path(temp) / "unused", limit=2)
            third = qc.scan(root, Path(temp) / "unused", limit=2)
            self.assertEqual((first["next_cursor"], second["next_cursor"], third["next_cursor"]),
                             (2, 4, 1))
            self.assertEqual(sum(x["inspected_this_tick"] for x in (first, second, third)), 6)


if __name__ == "__main__":
    unittest.main()
