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

    def test_intraword_markdown_emphasis_cannot_hide_duplicate_prose(self):
        with tempfile.TemporaryDirectory() as d:
            first = self.make(d, "chapter-01-part-001.md")
            second = Path(d) / "chapter-02-part-001.md"
            second.write_text(first.read_text().replace(
                "# Heading", "# A different heading").replace(
                "term0000", "term*0000*"))
            before = second.read_bytes()
            r = module.audit(Path(d), chapters=2,
                             chapter_target=300, total_target=600)
            self.assertTrue(any(x.startswith("duplicate_prose_body:")
                                for x in r["integrity_flags"]))
            self.assertFalse(r["length_and_structure_ready_for_independent_review"])
            self.assertFalse(r["commercial_release_allowed"])
            self.assertEqual(second.read_bytes(), before)

    def test_reused_long_paragraph_blocks_review_even_with_new_surrounding_prose(self):
        with tempfile.TemporaryDirectory() as d:
            repeated = " ".join("distinctword%04d" % i for i in range(140))
            first = Path(d) / "chapter-01-part-001.md"
            second = Path(d) / "chapter-02-part-001.md"
            first.write_text("# Chapter one\n\n" + repeated +
                             "\n\n" + " ".join("first%04d" % i for i in range(150)))
            second.write_text("# Chapter two\n\n" + repeated +
                              "\n\n" + " ".join("second%04d" % i for i in range(150)))
            before = (first.read_bytes(), second.read_bytes())
            result = module.audit(Path(d), chapters=2,
                                  chapter_target=250, total_target=500)
            self.assertFalse(any(x.startswith("duplicate_prose_body:")
                                 for x in result["integrity_flags"]))
            self.assertTrue(any(x.startswith("duplicate_long_paragraph:")
                                for x in result["integrity_flags"]))
            self.assertFalse(result["length_and_structure_ready_for_independent_review"])
            self.assertFalse(result["commercial_release_allowed"])
            self.assertEqual((first.read_bytes(), second.read_bytes()), before)

    def test_long_paragraph_intraword_markdown_cannot_hide_copy(self):
        with tempfile.TemporaryDirectory() as d:
            repeated = " ".join("distinctword%04d" % i for i in range(140))
            first = Path(d) / "chapter-01-part-001.md"
            second = Path(d) / "chapter-02-part-001.md"
            first.write_text("# First\n\n" + repeated +
                             "\n\n" + " ".join("first%04d" % i for i in range(150)))
            second.write_text("# Second\n\n" +
                              repeated.replace("distinctword0000", "distinctword*0000*") +
                              "\n\n" + " ".join("second%04d" % i for i in range(150)))
            before = (first.read_bytes(), second.read_bytes())
            result = module.audit(Path(d), chapters=2, chapter_target=250, total_target=500)
            self.assertTrue(any(flag.startswith("duplicate_long_paragraph:")
                                for flag in result["integrity_flags"]))
            self.assertFalse(result["length_and_structure_ready_for_independent_review"])
            self.assertEqual((first.read_bytes(), second.read_bytes()), before)

    def test_long_paragraph_identifier_underscore_stays_distinct(self):
        with tempfile.TemporaryDirectory() as d:
            repeated = " ".join("distinctword%04d" % i for i in range(140))
            first = Path(d) / "chapter-01-part-001.md"
            second = Path(d) / "chapter-02-part-001.md"
            first.write_text("# First\n\n" + repeated +
                             "\n\n" + " ".join("first%04d" % i for i in range(150)))
            second.write_text("# Second\n\n" +
                              repeated.replace("distinctword0000", "distinctword_0000") +
                              "\n\n" + " ".join("second%04d" % i for i in range(150)))
            result = module.audit(Path(d), chapters=2, chapter_target=250, total_target=500)
            self.assertFalse(any(flag.startswith("duplicate_long_paragraph:")
                                 for flag in result["integrity_flags"]))
            self.assertFalse(result["commercial_release_allowed"])

    def test_long_paragraph_distinct_numeric_scientific_identifiers(self):
        # IDs with the same alphabetic prefix but different numeric suffixes
        # must not collapse into identical tokens after an underscore.
        with tempfile.TemporaryDirectory() as d:
            first = Path(d) / "chapter-01-part-001.md"
            second = Path(d) / "chapter-02-part-001.md"
            prefix = " ".join("term_%04d" % i for i in range(140))
            changed = prefix.replace("term_0000", "term_9999")
            first.write_text("# First\n\n" + prefix +
                             "\n\n" + " ".join("first%04d" % i for i in range(150)))
            second.write_text("# Second\n\n" + changed +
                              "\n\n" + " ".join("second%04d" % i for i in range(150)))
            result = module.audit(Path(d), chapters=2, chapter_target=250, total_target=500)
            self.assertFalse(any(flag.startswith("duplicate_long_paragraph:")
                                 for flag in result["integrity_flags"]))
            self.assertFalse(result["commercial_release_allowed"])

    def test_invisible_unicode_and_compatibility_glyphs_cannot_hide_prose_copy(self):
        with tempfile.TemporaryDirectory() as d:
            first = self.make(d, "chapter-01-part-001.md")
            second = Path(d) / "chapter-02-part-001.md"
            altered = first.read_text().replace(
                "# Heading", "# Independent heading")
            altered = altered.replace("term0000", "term\u200b0000")
            altered = altered.replace("term0001", "\uff54erm0001")
            altered = altered.replace("term0002", "term\u00ad0002")
            second.write_text(altered)
            before = (first.read_bytes(), second.read_bytes())
            result = module.audit(Path(d), chapters=2,
                                  chapter_target=300, total_target=600)
            self.assertTrue(any(x.startswith("duplicate_prose_body:")
                                for x in result["integrity_flags"]))
            self.assertFalse(result["length_and_structure_ready_for_independent_review"])
            self.assertFalse(result["commercial_release_allowed"])
            self.assertEqual((first.read_bytes(), second.read_bytes()), before)

    def test_invisible_unicode_cannot_hide_long_paragraph_copy(self):
        with tempfile.TemporaryDirectory() as d:
            repeated = " ".join("distinctword%04d" % i for i in range(140))
            first = Path(d) / "chapter-01-part-001.md"
            second = Path(d) / "chapter-02-part-001.md"
            first.write_text("# First\n\n" + repeated +
                             "\n\n" + " ".join("first%04d" % i for i in range(150)))
            altered = repeated.replace("distinctword0000", "distinct\u200bword0000")
            altered = altered.replace("distinctword0001", "\uff44istinctword0001")
            second.write_text("# Second\n\n" + altered +
                              "\n\n" + " ".join("second%04d" % i for i in range(150)))
            before = (first.read_bytes(), second.read_bytes())
            result = module.audit(Path(d), chapters=2,
                                  chapter_target=250, total_target=500)
            self.assertTrue(any(x.startswith("duplicate_long_paragraph:")
                                for x in result["integrity_flags"]))
            self.assertFalse(result["length_and_structure_ready_for_independent_review"])
            self.assertFalse(result["commercial_release_allowed"])
            self.assertEqual((first.read_bytes(), second.read_bytes()), before)

    def test_distinct_long_paragraphs_are_not_falsely_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            for chapter in (1, 2):
                p = Path(d) / ("chapter-%02d-part-001.md" % chapter)
                p.write_text("# Chapter\n\n" +
                             " ".join("chapter%dterm%04d" % (chapter, i)
                                      for i in range(150)))
            result = module.audit(Path(d), chapters=2,
                                  chapter_target=100, total_target=200)
            self.assertFalse(any(x.startswith("duplicate_long_paragraph:")
                                 for x in result["integrity_flags"]))
            self.assertTrue(result["length_and_structure_ready_for_independent_review"])
            self.assertFalse(result["commercial_release_allowed"])

    def test_zero_width_reasoning_marker_cannot_bypass_private_gate(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, "chapter-01-part-001.md",
                          tail="<th\u200bink>internal reasoning</th\u200bink>")
            before = p.read_bytes()
            result = module.audit(Path(d), chapters=1,
                                  chapter_target=300, total_target=300)
            self.assertTrue(any(x.startswith("unsafe_content_marker:")
                                for x in result["integrity_flags"]))
            self.assertFalse(result["length_and_structure_ready_for_independent_review"])
            self.assertFalse(result["commercial_release_allowed"])
            self.assertEqual(p.read_bytes(), before)

    def test_fullwidth_reasoning_and_invisible_citation_markers_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, "chapter-01-part-001.md",
                          tail="<\uff54\uff48\uff49\uff4e\uff4b>hidden</\uff54\uff48\uff49\uff4e\uff4b> [citat\u200bion needed]")
            before = p.read_bytes()
            result = module.audit(Path(d), chapters=1,
                                  chapter_target=300, total_target=300)
            self.assertTrue(any(x.startswith("unsafe_content_marker:")
                                for x in result["integrity_flags"]))
            self.assertFalse(result["commercial_release_allowed"])
            self.assertEqual(p.read_bytes(), before)

    def test_bidi_controls_cannot_hide_private_reasoning_tokens(self):
        # The final accept gate already strips bidi controls. The independent
        # private read-only auditor must not allow the same evasion.
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, "chapter-01-part-001.md",
                          tail="<th\u202eink>internal</th\u202eink> "
                               "<\u2066think\u2069>hidden</think>")
            before = p.read_bytes()
            result = module.audit(Path(d), chapters=1,
                                  chapter_target=300, total_target=300)
            self.assertTrue(any(flag.startswith("unsafe_content_marker:")
                                for flag in result["integrity_flags"]))
            self.assertFalse(result["length_and_structure_ready_for_independent_review"])
            self.assertFalse(result["commercial_release_allowed"])
            self.assertEqual(p.read_bytes(), before)

    def test_direction_marks_cannot_hide_reasoning_in_private_audit(self):
        # LRM, RLM and Arabic Letter Mark are invisible formatting controls.
        # They must not conceal leaked model reasoning from private review.
        for control in ("\\u200e", "\\u200f", "\\u061c"):
            with self.subTest(control=repr(control)):
                with tempfile.TemporaryDirectory() as d:
                    p = self.make(d, "chapter-01-part-001.md",
                                  tail="<th" + control + "ink>hidden</think>")
                    before = p.read_bytes()
                    result = module.audit(Path(d), chapters=1,
                                          chapter_target=300, total_target=300)
                    self.assertTrue(any(x.startswith("unsafe_content_marker:")
                                        for x in result["integrity_flags"]))
                    self.assertFalse(result["length_and_structure_ready_for_independent_review"])
                    self.assertFalse(result["commercial_release_allowed"])
                    self.assertEqual(p.read_bytes(), before)

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
