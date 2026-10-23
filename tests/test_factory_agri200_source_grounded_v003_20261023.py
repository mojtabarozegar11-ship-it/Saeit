"""Validate real v003 reauthoring, immutable evidence, independent mechanical QC."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, str(
        Path(__file__).resolve().parents[1] / "scripts" / file))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


writer = load("revision_writer", "factory_agri200_source_grounded_v003_20261023.py")
qc = load("revision_qc", "factory_agri200_source_grounded_v003_qc_20261023.py")
zipper = load("revision_zip", "factory_agri200_downloadable_20261023.py")


class Lib:
    def private_dir(self, path):
        path.mkdir(parents=True, exist_ok=True)

    def digest(self, value):
        return hashlib.sha256(json.dumps(value, ensure_ascii=False,
            sort_keys=True, separators=(",", ":")).encode("utf8")).hexdigest()

    def read(self, path):
        return json.loads(path.read_text(encoding="utf8"))

    def once(self, path, value):
        self.private_dir(path.parent)
        content = json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n"
        if path.exists():
            if path.read_text(encoding="utf8") != content:
                raise RuntimeError("IMMUTABLE_CONFLICT")
            return False
        path.write_text(content, encoding="utf8")
        return True


def fixture():
    sources = [
        {"id": "src%02d" % n, "title": "Original research paper %d on crop nitrogen budgeting" % n,
         "publisher": "Independent agricultural institute %d" % n,
         "url": "https://example.org/paper/%d" % n,
         "doi": "10.1234/agronomy%d" % n, "publication_year": 2020 + n % 5}
        for n in range(1, 6)
    ]
    claims = [
        {"id": "clm%02d" % n,
         "statement": ("The indexed abstract examines interactions between soil nitrogen "
                       "management and crop growth under a bounded environmental study design, "
                       "but the indexed text does not establish a universal field-rate recommendation."),
         "source_ids": ["src%02d" % n]}
        for n in range(1, 6)
    ]
    chapters = [
        {"unit": n, "title_fa": "بررسی متغیرهای نیتروژن و ویژگی خاک در بخش %s" % n,
         "title_en": "Soil nitrogen and experimental context analysis %d" % n,
         "source_claim_id": "clm%02d" % n,
         "source_ids": ["src%02d" % n]}
        for n in range(1, 6)
    ]
    design = {"chapters": chapters}
    research = {"sources": sources, "claims": claims, "locale_scopes": {
        "fa-IR": "مطالعه و نقد شواهد نیتروژن خاک با در نظر گرفتن شرایط ایران",
        "en-US": "Critical agronomic literature reading with global applicability limits"}}
    editions = {
        "fa-IR": {"title": "راهنمای تحلیل پژوهش نیتروژن خاک", "audience": "کارشناسان و پژوهشگران"},
        "en-US": {"title": "Evidence workbench for soil nitrogen studies",
                  "audience": "Agricultural researchers"}}
    return design, research, editions, {s["id"]: s for s in sources}, {
        c["id"]: c for c in claims}


class RevisionTests(unittest.TestCase):
    def test_bilingual_specific_sections_and_no_repeated_paragraphs(self):
        design, research, editions, sources, claims = fixture()
        for loc in ("fa-IR", "en-US"):
            raw = writer.edition(design, research, editions, sources, claims, loc)
            self.assertGreaterEqual(len(raw.decode().split()), 1200)
            self.assertIn(b"src01", raw)
            self.assertIn(b"clm05", raw)
            self.assertNotIn(b"QC1000: APPROVED", raw)
            self.assertLess(len(raw), 700_000)

    def test_independent_mechanical_qc_and_immutable_artifact(self):
        design, research, editions, sources, claims = fixture()
        lib = Lib()
        name = "WO-00000001--r001.json"
        original = {"order_id": "WO-00000001"}
        ticket = {"must_resubmit_new_artifact_and_repeat_strict_qc": True}
        with tempfile.TemporaryDirectory() as tmp:
            area = Path(tmp) / "production-instructions"
            (area / "stage-05/completed-drafts").mkdir(parents=True)
            (area / "stage-05/strict-qc-rework").mkdir(parents=True)
            lib.once(area / "stage-05/completed-drafts" / name, original)
            lib.once(area / "stage-05/strict-qc-rework" / name, ticket)
            stage5 = type("Stage5", (), {"write_once": staticmethod(
                lambda path, body, lib: (path.parent.mkdir(parents=True, exist_ok=True),
                    path.write_bytes(body)) if not path.exists() else None)})
            with patch.object(writer, "catalog", return_value=(
                design, research, editions, original, ticket, sources, claims)):
                self.assertTrue(writer.author_one(area, name, lib, stage5, zipper))
                self.assertFalse(writer.author_one(area, name, lib, stage5, zipper))
            result = qc.check_one(area, name, lib, None)
            self.assertTrue(result["mechanical_integrity_pass"])
            self.assertFalse(result["independent_quality1000_approved"])
            self.assertFalse(result["commercial_release"])
            self.assertEqual(result["revision"], 3)
            self.assertLessEqual(result["measurements"]["fa-IR"]["duplicate_fraction"], .1)
            self.assertLessEqual(result["measurements"]["en-US"]["duplicate_fraction"], .1)

    def test_tampering_v003_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            area = Path(temp)
            with self.assertRaisesRegex(RuntimeError, "REVISED_ARCHIVE_TRAVERSAL"):
                qc.safe_archive(area, "../escape.zip")


if __name__ == "__main__":
    unittest.main()
