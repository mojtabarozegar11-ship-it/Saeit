"""Check MOJ PROP's language-cluster repair is scoped and reversible."""
from pathlib import Path
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/"scripts"/"mojprop_20lang_equivalence_20261121.py"
BUILDER=ROOT/"scripts"/"mojprop_multilang_20261121_build.py"

class HreflangEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location("mojprop_global_builder",BUILDER)
        cls.mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.source=TARGET.read_text(encoding="utf-8")
    def test_official_page_is_not_a_localized_educational_page(self):
        self.assertIn("result[PROGRAM]=english_after.encode",self.source)
        self.assertIn('english.decode().replace(oldhead,"",1)',self.source)
        self.assertIn('original_hreflang=mod.hreflangs()',self.source)
        self.assertIn('NEW=BASE/"en"/"index.html"',self.source)
        self.assertIn('EXPECTED_PROGRAM_SHA=',self.source)
        self.assertIn('EXPECTED_SITEMAP_SHA=',self.source)
        self.assertIn('EXPECTED_SELECTOR_SHA=',self.source)
    def test_20_educational_languages_and_valid_google_alternates(self):
        self.assertEqual(len(self.mod.L),19)
        self.assertIn('pcm',self.mod.NAMES)
        self.assertNotIn('pcm',self.mod.VALID)
        self.assertIn('en',self.mod.VALID)
        self.assertEqual(len(self.mod.VALID),19)
        patched_path=lambda c: "/moj-prop/languages/en/" if c=="en" else self.mod.path(c)
        tags={code:"https://mojplaywin.com"+patched_path(code) for code in self.mod.VALID}
        tags["x-default"]="https://mojplaywin.com/moj-prop/languages/"
        self.assertEqual(len(tags),20)
        self.assertNotIn('pcm',tags)
        self.assertNotEqual(tags['en'],"https://mojplaywin.com/moj-prop/")
        self.assertEqual(tags['ar-EG'],"https://mojplaywin.com/moj-prop/languages/ar-eg/")
    def test_no_checkout_factory_or_database_mutations(self):
        self.assertNotIn("subprocess",self.source)
        self.assertNotIn("sqlite3",self.source)
        self.assertNotIn("request.POST",self.source)
        self.assertNotIn("https://api.trongrid",self.source)
        self.assertIn("BACKUP_VERIFIED",self.source)
        self.assertIn('if PRIVATE.exists() or PRIVATE.is_symlink()',self.source)
    def test_expected_sitemap_and_canonical_guards(self):
        self.assertIn("sitemap_new.count(\"<loc>\")!=35",self.source)
        self.assertIn('Reciprocal alternate mismatch',self.source)
        self.assertIn('Wrong self-canonical',self.source)
        self.assertIn('English language choice missing',self.source)

if __name__=="__main__":
    unittest.main()
