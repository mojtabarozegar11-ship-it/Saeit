"""Offline regression for fail-closed private manuscript audit."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/factory_private_manuscript_audit_20261026.py"
spec = importlib.util.spec_from_file_location("private_manuscript_audit", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PrivateAuditTests(unittest.TestCase):
    def make(self, folder, name, words=320, tail=""):
        path = Path(folder) / name
        path.write_text("# Heading\n\n" + " ".join("term%04d" % i for i in range(words)) + ". " + tail)
        return path

    def test_incomplete_remains_unapproved_and_immutable(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, "chapter-01-part-001.md")
            before = p.read_bytes()
            r = module.audit(Path(d), chapters=2, chapter_target=300, total_target=600)
            self.assertEqual(r["total_substantive_words"], 320)
            self.assertEqual(r["chapters_below_target"], [2])
            self.assertFalse(r["commercial_release_allowed"])
            self.assertFalse(r["length_and_structure_ready_for_independent_review"])
            self.assertEqual(p.read_bytes(), before)

    def test_length_ready_does_not_grant_commercial_approval(self):
        with tempfile.TemporaryDirectory() as d:
            self.make(d, "chapter-01-part-001.md")
            self.make(d, "chapter-02-part-001.md", tail="Distinct chapter prose.")
            r = module.audit(Path(d), chapters=2, chapter_target=300, total_target=600)
            self.assertTrue(r["length_and_structure_ready_for_independent_review"])
            self.assertFalse(r["quality1000_approved"])
            self.assertFalse(r["independent_scientific_review_passed"])
            self.assertFalse(r["commercial_release_allowed"])
            self.assertEqual(len(r["part_evidence"]), 2)

    def test_duplicate_segment_content_blocks_independent_review(self):
        with tempfile.TemporaryDirectory() as d:
            first = self.make(d, "chapter-01-part-001.md")
            second = Path(d) / "chapter-02-part-001.md"
            second.write_bytes(first.read_bytes())
            before = second.read_bytes()
            r = module.audit(Path(d), chapters=2, chapter_target=300, total_target=600)
            self.assertEqual(r["chapters_below_target"], [])
            self.assertTrue(any(x.startswith("duplicate_segment_content:")
                                for x in r["integrity_flags"]))
            self.assertFalse(r["length_and_structure_ready_for_independent_review"])
            self.assertFalse(r["commercial_release_allowed"])
            self.assertEqual(second.read_bytes(), before)

    def test_reheaded_duplicate_prose_blocks_review(self):
        with tempfile.TemporaryDirectory() as d:
            first = self.make(d, "chapter-01-part-001.md")
            second = Path(d) / "chapter-02-part-001.md"
            second.write_text(first.read_text().replace(
                "# Heading", "# A different chapter heading"))
            before = second.read_bytes()
            r = module.audit(Path(d), chapters=2, chapter_target=300, total_target=600)
            self.assertTrue(any(x.startswith("duplicate_prose_body:")
                                for x in r["integrity_flags"]))
            self.assertFalse(r["length_and_structure_ready_for_independent_review"])
            self.assertFalse(r["commercial_release_allowed"])
            self.assertEqual(second.read_bytes(), before)

    def test_reheaded_whitespace_variant_duplicate_blocks_review(self):
        # Altering tabs or repeated spaces must not bypass the prose hash.
        with tempfile.TemporaryDirectory() as d:
            first = self.make(d, "chapter-01-part-001.md")
            second = Path(d) / "chapter-02-part-001.md"
            variant = first.read_text().replace(
                "# Heading", "# A different heading")
            second.write_text(variant.replace(" ", " \t  "))
            before = second.read_bytes()
            r = module.audit(Path(d), chapters=2,
                             chapter_target=300, total_target=600)
            self.assertTrue(any(x.startswith("duplicate_prose_body:")
                                for x in r["integrity_flags"]))
            self.assertFalse(r["length_and_structure_ready_for_independent_review"])
            self.assertFalse(r["commercial_release_allowed"])
            self.assertEqual(second.read_bytes(), before)

    def test_reheaded_markdown_emphasis_variant_duplicate_blocks_review(self):
        # Adding bold/code emphasis to copied prose must not bypass duplicate QC.
        with tempfile.TemporaryDirectory() as d:
            first = self.make(d, "chapter-01-part-001.md")
            second = Path(d) / "chapter-02-part-001.md"
            variant = first.read_text().replace(
                "# Heading", "# A different heading")
            variant = variant.replace("term0000", "**term0000**")
            variant = variant.replace("term0001", "`term0001`")
            second.write_text(variant)
            before = second.read_bytes()
            r = module.audit(Path(d), chapters=2,
                             chapter_target=300, total_target=600)
            self.assertTrue(any(x.startswith("duplicate_prose_body:")
                                for x in r["integrity_flags"]))
            self.assertFalse(r["length_and_structure_ready_for_independent_review"])
            self.assertFalse(r["commercial_release_allowed"])
            self.assertEqual(second.read_bytes(), before)

    def test_inline_identifier_underscore_is_not_removed(self):
        # A substantive identifier change must not be mistaken for Markdown.
        with tempfile.TemporaryDirectory() as d:
            self.make(d, "chapter-01-part-001.md")
            second = Path(d) / "chapter-02-part-001.md"
            first_text = (Path(d) / "chapter-01-part-001.md").read_text()
            second.write_text(first_text.replace(
                "# Heading", "# A different heading").replace(
                "term0000", "term_0000"))
            r = module.audit(Path(d), chapters=2,
                             chapter_target=300, total_target=600)
            self.assertFalse(any(x.startswith("duplicate_prose_body:")
                                 for x in r["integrity_flags"]))
            self.assertFalse(r["commercial_release_allowed"])

    def test_gap_and_reasoning_marker_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            self.make(d, "chapter-01-part-002.md", tail="<think>secret</think>")
            r = module.audit(Path(d), chapters=1, chapter_target=300, total_target=300)
            self.assertTrue(any(x.startswith("noncontiguous_parts") for x in r["integrity_flags"]))
            self.assertTrue(any(x.startswith("unsafe_content_marker") for x in r["integrity_flags"]))
            self.assertFalse(r["length_and_structure_ready_for_independent_review"])

    def test_symlink_and_unknown_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, "chapter-01-part-001.md")
            (Path(d) / "chapter-01-part-002.md").symlink_to(p)
            (Path(d) / "unknown.txt").write_text("unsafe")
            r = module.audit(Path(d), chapters=1, chapter_target=300, total_target=300)
            self.assertEqual(len(r["integrity_flags"]), 2)
            self.assertFalse(r["length_and_structure_ready_for_independent_review"])

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as d:
            r = module.audit(Path(d))
            self.assertEqual(len(r["chapters_below_target"]), 30)
            self.assertEqual(r["total_substantive_words"], 0)


if __name__ == "__main__":
    unittest.main()
