"""End-to-end synthetic tests for Astra's read-only commercial release-gap gate."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "astra_v2_release_gate.py"
spec = importlib.util.spec_from_file_location("astra_release_gate_test", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ReleaseGapTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.private = self.home / "private"
        self.source = self.home / "source"
        self.private.mkdir()
        self.source.mkdir()
        self.revisions = {}
        db = self.private / "queue.sqlite3"
        with sqlite3.connect(db) as con:
            con.execute(
                "CREATE TABLE jobs (builder TEXT, stage TEXT, artifact_sha TEXT)"
            )
        for builder, (slug, files) in gate.SOURCE_FAMILIES.items():
            folder = self.source / "product_prototypes" / slug
            folder.mkdir(parents=True)
            payloads = {}
            for name in files:
                contents = (builder + ":" + name + ":synthetic-example\n").encode()
                (folder / name).write_bytes(contents)
                payloads[name] = contents
            revision, mapped = gate.source_revision(self.source, builder, slug, files)
            self.assertEqual(mapped, payloads)
            self.revisions[builder] = revision
            path = self.private / ("artifact-" + revision + ".zip")
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                for name, blob in payloads.items():
                    z.writestr(slug + "/" + name, blob)
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            report = {
                "source_builder": builder,
                "product_slug": slug,
                "source_digest": revision,
                "included_files": sorted(files),
                "artifact_sha256": sha,
                "technical_regression": "PASSED",
                "integrity_check": "PASSED",
                "quality_score": None,
            }
            report.update({k: False for k in gate.MANDATORY_FALSE})
            (self.private / ("qa-" + revision + ".json")).write_text(
                json.dumps(report), encoding="utf-8")
            with sqlite3.connect(db) as con:
                con.execute("INSERT INTO jobs VALUES (?,?,?)",
                            (builder, "PRIVATE_QA_PASSED", sha))

    def report(self):
        return gate.evaluate(self.private, self.source)

    def test_three_technically_integral_prototypes_remain_commercially_blocked(self):
        result = self.report()
        self.assertEqual(result["verified_private_technical_families"], 3)
        self.assertEqual(result["technical_integrity_gate"], "PASS")
        self.assertEqual(result["commercially_qualified_products"], 0)
        self.assertEqual(result["payment_attempts"], 0)
        self.assertEqual(result["factory_mutations"], 0)
        for item in result["families"]:
            self.assertEqual(item["technical_artifact_integrity"], "VERIFIED")
            self.assertIsNone(item["commercial_quality_score"])
            self.assertFalse(item["commercial_release_authorized"])
            self.assertIn("VERIFY_BUYER_PROBLEM", item["next_evidence_work"][0])

    def test_broken_zip_does_not_pass_hash_and_integrity(self):
        builder = next(iter(gate.SOURCE_FAMILIES))
        path = self.private / ("artifact-" + self.revisions[builder] + ".zip")
        path.write_bytes(path.read_bytes() + b"untrusted bytes")
        result = self.report()
        self.assertEqual(result["verified_private_technical_families"], 2)
        self.assertEqual(result["technical_integrity_gate"], "FAIL")

    def test_promoted_sale_flags_are_rejected_even_with_valid_zip(self):
        builder = next(iter(gate.SOURCE_FAMILIES))
        path = self.private / ("qa-" + self.revisions[builder] + ".json")
        content = json.loads(path.read_text())
        content["sale_ready"] = True
        content["quality_score"] = 100
        path.write_text(json.dumps(content))
        result = self.report()
        self.assertEqual(result["verified_private_technical_families"], 2)
        self.assertEqual(result["commercially_qualified_products"], 0)

    def test_manifest_with_incorrect_source_digest_is_blocked(self):
        builder = next(iter(gate.SOURCE_FAMILIES))
        path = self.private / ("qa-" + self.revisions[builder] + ".json")
        content = json.loads(path.read_text())
        content["source_digest"] = "0" * 64
        path.write_text(json.dumps(content))
        self.assertEqual(self.report()["verified_private_technical_families"], 2)

    def test_missing_queue_acceptance_blocks_artifact_claim(self):
        with sqlite3.connect(self.private / "queue.sqlite3") as con:
            con.execute("UPDATE jobs SET stage='QUEUED' WHERE builder=?",
                        (next(iter(gate.SOURCE_FAMILIES)),))
        self.assertEqual(self.report()["verified_private_technical_families"], 2)

    def test_source_mutation_invalidates_previous_artifact_revision(self):
        builder, (slug, files) = next(iter(gate.SOURCE_FAMILIES.items()))
        (self.source / "product_prototypes" / slug / files[0]).write_text(
            "unreviewed source mutation")
        self.assertEqual(self.report()["verified_private_technical_families"], 2)

    def test_foreign_files_do_not_get_deleted_or_counted(self):
        foreign = self.private / "owner-notes.txt"
        foreign.write_text("not an Astra product")
        original = foreign.read_bytes()
        self.report()
        self.assertEqual(foreign.read_bytes(), original)

    def test_symlinked_manifest_never_passes(self):
        builder = next(iter(gate.SOURCE_FAMILIES))
        old = self.private / ("qa-" + self.revisions[builder] + ".json")
        target = self.home / "foreign-manifest.json"
        target.write_bytes(old.read_bytes())
        old.unlink()
        old.symlink_to(target)
        self.assertEqual(self.report()["verified_private_technical_families"], 2)

    def test_reject_symlinked_private_root(self):
        shadow = self.home / "shadow"
        shadow.symlink_to(self.private, target_is_directory=True)
        with self.assertRaises(ValueError):
            gate.evaluate(shadow, self.source)

    def test_cli_strict_is_successful_but_cannot_release(self):
        cmd = [sys.executable, str(SCRIPT), "--private-root", str(self.private),
               "--active-source", str(self.source), "--strict-technical"]
        db_before = hashlib.sha256((self.private / "queue.sqlite3").read_bytes()).hexdigest()
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["commercially_qualified_products"], 0)
        self.assertIn("ASTRA_PRIVATE_TECHNICAL_FAMILIES=3", done.stderr)
        self.assertEqual(db_before, hashlib.sha256(
            (self.private / "queue.sqlite3").read_bytes()).hexdigest())

    def test_cli_strict_fails_closed_on_missing_package(self):
        builder = next(iter(gate.SOURCE_FAMILIES))
        (self.private / ("artifact-" + self.revisions[builder] + ".zip")).unlink()
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "--private-root", str(self.private),
             "--active-source", str(self.source), "--strict-technical"],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(done.returncode, 2)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["verified_private_technical_families"], 2)
        self.assertEqual(payload["commercially_qualified_products"], 0)


if __name__ == "__main__":
    unittest.main()
