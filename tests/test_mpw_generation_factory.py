"""Real Python Gen65 source-generation regression tests, fully isolated."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from mpw_v91_port import generation_factory as g


def evidence(n, ready=False, quality=92, sources=1):
    return [{"id": "audit-%03d" % i, "kind": "research_digest", "quality": quality,
             "source_count": sources, "ready": ready} for i in range(n)]


class GenerationFactoryTests(unittest.TestCase):
    def test_gen65_is_actually_generated_with_new_callable_code_and_sha_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = g.produce(root, evidence(2))
            self.assertEqual(result["status"], "generated_new_quarantined_python_generation")
            self.assertEqual(result["generation"], 65)
            self.assertEqual(result["parent_generation"], 64)
            self.assertFalse(result["promoted"])
            code = (root / "generations" / "generation65.py").read_bytes()
            manifest = json.loads((root / "generations" / "generation65.json").read_text())
            self.assertEqual(manifest["code_sha256"], hashlib.sha256(code).hexdigest())
            self.assertFalse(manifest["executed_in_production"])
            self.assertFalse(manifest["promotion_authorized"])
            # Inspect the generated fixed-recipe Python module, not production imports.
            module = {}
            exec(compile(code, "generated_gen65.py", "exec"), module)
            controller = module["Generation65Controller"]()
            self.assertEqual(controller.generation, 65)
            self.assertEqual(controller.parent_generation, 64)
            self.assertEqual(controller.classify(98, 2, True),
                             "candidate_ready_for_human_review")
            self.assertEqual(controller.classify(99, 8, False),
                             "abstain_unverified")
            self.assertEqual(controller.classify(92, 1, True),
                             "hold_for_review")
            self.assertFalse(controller.benchmark(evidence(2))["approved"])
            self.assertIs(type(module["wilson_precision_lower"](8, 10)), float)

    def test_one_generation_per_evidence_set_no_minute_inflation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            g.produce(root, evidence(2))
            for _ in range(100):
                result = g.produce(root, evidence(2))
                self.assertEqual(result["status"], "current_candidate_retained_pending_evidence")
                self.assertEqual(result["generation"], 65)
            self.assertEqual(len(list((root / "generations").iterdir())), 2)

    def test_future_gen_requires_twelve_results_new_evidence_and_verified_improvement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            g.produce(root, evidence(2))
            self.assertEqual(g.produce(root, evidence(13), False)["generation"], 65)
            result = g.produce(root, evidence(13), True)
            self.assertEqual(result["generation"], 66)
            self.assertEqual(result["status"], "generated_new_quarantined_python_generation")
            module = {}
            code = (root / "generations" / "generation66.py").read_bytes()
            exec(compile(code, "candidate66.py", "exec"), module)
            self.assertEqual(module["Generation66Controller"]().generation, 66)
            self.assertEqual(g.produce(root, evidence(13), True)["generation"], 66)

    def test_cross_tenant_unverified_bool_and_duplicates_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples = evidence(2)
            samples[0]["quality"] = True
            with self.assertRaisesRegex(ValueError, "unverified_generation_evidence"):
                g.produce(root, samples)
            samples = evidence(2)
            samples[1]["id"] = samples[0]["id"]
            with self.assertRaisesRegex(ValueError, "unverified_generation_evidence"):
                g.produce(root, samples)

    def test_tampering_with_generated_python_blocks_next_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            g.produce(root, evidence(2))
            script = root / "generations" / "generation65.py"
            script.write_text(script.read_text() + "\n# tampered")
            with self.assertRaisesRegex(RuntimeError, "generation_code_provenance_mismatch"):
                g.produce(root, evidence(30), True)

    def test_read_only_validated_manifest_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            g.produce(root, evidence(2))
            folder = root / "generations"
            self.assertEqual(folder.stat().st_mode & 0o077, 0)
            for item in folder.iterdir():
                self.assertEqual(item.stat().st_mode & 0o077, 0)
            (folder / "generation65.json").unlink()
            (folder / "generation65.json").symlink_to("/etc/passwd")
            with self.assertRaisesRegex(RuntimeError, "unsafe_generation_manifest"):
                g.produce(root, evidence(2))

    def test_future_candidate_is_not_auto_promoted_to_master(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            g.produce(root, evidence(2))
            g.produce(root, evidence(20, ready=False), True)
            record = json.loads((root / "generations" / "generation66.json").read_text())
            self.assertFalse(record["auto_deploy"])
            self.assertFalse(record["financial_authority"])
            self.assertTrue(record["requires_benchmark_and_human_approval"])


if __name__ == "__main__":
    unittest.main()
