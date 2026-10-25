"""Regression for fail-closed private AGRI checkpoint integrity (synthetic text only)."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "factory_agri150k_private_checkpoint_integrity_agent_v1.py"
spec = importlib.util.spec_from_file_location("private_integrity", SCRIPT)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


def _chunk(seed=0):
    return "# Synthetic fixture, not a book chapter\n\n" + " ".join(
        "botanicalword" + str(seed * 10000 + i) for i in range(700)
    ) + "\n"


class PrivateCheckpointIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = {
            "schema": "saeit.agri150k.private-draft-checkpoint.v6",
            "product_id": "AGRI-001",
            "title": "Houseplant Rescue Guide",
            "language": "en-US",
            "publication_allowed": False,
            "qc1000_approved": False,
            "independent_scientific_review": False,
            "mechanical_prose_words_unreviewed_gate_v1": 0,
            "chunks": [],
        }
        self.add_chunk(1)

    def save(self):
        (self.root / "manifest.json").write_text(
            json.dumps(self.manifest), encoding="utf-8"
        )

    def add_chunk(self, part, seed=None):
        seed = part if seed is None else seed
        name = f"chapter-03-part-{part:03d}.md"
        raw = _chunk(seed).encode("utf-8")
        (self.root / name).write_bytes(raw)
        count = len(agent._gate().prose_tokens(raw.decode()))
        self.manifest["chunks"].append({
            "chapter": 3, "part": part, "file": name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "mechanical_prose_words_unreviewed_gate_v1": count,
            "publication_allowed": False,
            "qc1000_approved": False,
            "independent_scientific_review": False,
        })
        self.manifest["mechanical_prose_words_unreviewed_gate_v1"] += count
        self.save()

    def test_valid_checkpoint_is_only_mechanically_approved(self):
        out = agent.audit(self.root)
        self.assertEqual(out["chunks_checked"], 1)
        self.assertEqual(out["unreviewed_mechanical_words"], 700)
        self.assertFalse(out["publication_allowed"])
        self.assertFalse(out["independent_scientific_review"])
        self.assertNotIn(str(self.root), json.dumps(out))

    def test_mutated_chunk_blocks(self):
        with (self.root / "chapter-03-part-001.md").open("ab") as f:
            f.write(b" changed")
        with self.assertRaisesRegex(agent.IntegrityBlocked, "SHA256"):
            agent.audit(self.root)

    def test_false_manifest_count_blocks(self):
        self.manifest["mechanical_prose_words_unreviewed_gate_v1"] += 1
        self.save()
        with self.assertRaisesRegex(agent.IntegrityBlocked, "TOTAL"):
            agent.audit(self.root)

    def test_symlink_chunk_blocks(self):
        chunk = self.root / "chapter-03-part-001.md"
        chunk.unlink()
        outside = self.root.parent / (self.root.name + "-outside.txt")
        outside.write_text(_chunk(), encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        chunk.symlink_to(outside)
        with self.assertRaisesRegex(agent.IntegrityBlocked, "SYMLINK"):
            agent.audit(self.root)

    def test_untracked_file_blocks(self):
        (self.root / "chapter-03-part-002.md").write_text(_chunk(2))
        with self.assertRaisesRegex(agent.IntegrityBlocked, "UNTRACKED"):
            agent.audit(self.root)

    def test_release_flag_blocks(self):
        self.manifest["publication_allowed"] = True
        self.save()
        with self.assertRaisesRegex(agent.IntegrityBlocked, "RELEASE"):
            agent.audit(self.root)

    def test_duplicate_second_chunk_blocks(self):
        self.add_chunk(2, seed=1)
        with self.assertRaisesRegex(agent.IntegrityBlocked, "REPETITION"):
            agent.audit(self.root)

    def test_distinct_second_chunk_passes(self):
        self.add_chunk(2)
        out = agent.audit(self.root)
        self.assertEqual(out["chunks_checked"], 2)
        self.assertEqual(out["unreviewed_mechanical_words"], 1400)


if __name__ == "__main__":
    unittest.main()
