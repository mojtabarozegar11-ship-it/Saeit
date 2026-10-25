import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest

GATE_PATH = Path(__file__).resolve().parents[1] / "scripts/factory_leech_prepublish_gate_20261025.py"
spec = importlib.util.spec_from_file_location("leech_prepublish_gate", GATE_PATH)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

def alpha(n):
    digits = []
    for _ in range(5):
        digits.append(chr(97 + (n % 26)))
        n //= 26
    return "w" + "".join(reversed(digits))

class FakeWriter:
    ORDER = "WO-26102501"
    REQUIRED_CHAPTERS = 30

    def __init__(self, root, complete=False):
        self.PRIVATE = Path(root) / "private"
        self.PRIVATE.mkdir(mode=0o700)
        self.chapters = [{"chapter_title": "Farm Operating Unit " + str(i)}
                         for i in range(1, 31)]
        self.chunks = {i:[] for i in range(1,31)}
        if complete:
            for chapter in range(1,31):
                unique = [alpha((chapter-1)*5298+i) for i in range(5298)]
                body = "# Farm Unit A\n# Farm Unit B\n# Farm Unit C\nfarm operator " + " ".join(unique)
                self.chunks[chapter] = [(1,body)]
            counts,total,_,_ = self.state(self.chunks)
            (self.PRIVATE / "status.json").write_text(json.dumps({
                "order_id":self.ORDER, "total_substantive_draft_words":total,
                "per_chapter_words":counts, "quality1000_approved":False,
                "commercial_release":False, "public_distribution_allowed":False
            }),encoding="utf8")
    def source_evidence(self):
        return ({"official_title":"Professional Leech Farm Operations"},
                self.chapters, [{"id":"source-"+str(i)} for i in range(7)])
    def words(self,txt):
        return re.findall(r"[a-z][a-z'-]*",
            "\n".join(line for line in txt.lower().splitlines()
                      if not line.lstrip().startswith("#")))
    def list_parts(self):
        return self.chunks
    def state(self,chunks):
        counts = {str(i):sum(len(self.words(t)) for _,t in chunks[i])
                  for i in range(1,31)}
        next_chapter=next((i for i in range(1,31)
                            if counts[str(i)] < 5300),None)
        return counts,sum(counts.values()),next_chapter,1 if next_chapter else None
    def safe_json(self,path):
        return json.loads(path.read_text(encoding="utf8"))
    def save_once(self,path,payload):
        assert not path.exists()
        path.write_bytes(payload)
    def save_atomic(self,path,payload):
        path.write_bytes(payload)

class LeechCommercialPreflightTests(unittest.TestCase):
    def test_incomplete_never_claims_quality1000(self):
        with tempfile.TemporaryDirectory() as d:
            result=gate.verify("finalize",writer=FakeWriter(d))
            self.assertEqual(result["state"],"authoring_in_progress")
            self.assertFalse(result["quality1000_approved"])
            self.assertFalse(result["publication_authorized"])
            self.assertFalse((Path(d)/"private"/"complete-unreviewed.md").exists())

    def test_full_length_repairs_missing_assembly_without_publishing(self):
        with tempfile.TemporaryDirectory() as d:
            writer=FakeWriter(d,complete=True)
            result=gate.verify("finalize",writer=writer)
            self.assertEqual(result["words"],159000)
            self.assertEqual(result["state"],"ready_for_independent_scientific_editorial_review")
            self.assertTrue(result["assembled_book_regenerated_safely"])
            self.assertFalse(result["scientific_content_approved"])
            self.assertFalse(result["quality1000_approved"])
            self.assertFalse(result["publication_authorized"])
            book=writer.PRIVATE/"complete-unreviewed.md"
            self.assertEqual(book.read_bytes()[:2],b"# ")
            again=gate.verify("finalize",writer=writer)
            self.assertFalse(again["assembled_book_regenerated_safely"])
            book.write_text("tampered",encoding="utf8")
            failed=gate.verify("inspect",writer=writer)
            self.assertIn("ASSEMBLED_MANUSCRIPT_MISMATCH",failed["issues"])
            self.assertFalse(failed["technical_integrity_passed"])

    def test_forged_quality_approval_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            writer=FakeWriter(d,complete=True)
            path=writer.PRIVATE/"status.json"
            data=json.loads(path.read_text())
            data["quality1000_approved"]=True
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(RuntimeError,"RELEASE_GATE"):
                gate.verify("finalize",writer=writer)

if __name__ == "__main__":
    unittest.main()
