"""Public Moj Prop education library: no broken relative links or draft-only copy."""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"docs/mojprop/education"
GUIDES=(
    "starter30-buyer-guide.md",
    "position-sizing-and-drawdown.md",
    "consistency-rule-explained.md",
    "simulated-vs-live-trading.md",
    "sixty-day-practice-plan.md",
    "secure-trx-invoice-checklist.md",
)

class MojPropEducationPublicationTests(unittest.TestCase):
    def test_root_readme_links_to_public_education_hub(self):
        repo_readme=(ROOT.parents[2]/"README.md").read_text(encoding="utf-8")
        self.assertEqual(repo_readme.count("docs/mojprop/education/README.md"),1)
        self.assertIn("five free guides to simulated trading",repo_readme.lower())
        self.assertIn("starter30-buyer-guide.md",repo_readme)
        self.assertIn("30 TRX simulated challenge",repo_readme)

    def test_public_guide_catalog_is_complete(self):
        self.assertEqual({p.name for p in ROOT.glob("*.md")},set(GUIDES)|{"README.md"})
        index=(ROOT/"README.md").read_text(encoding="utf-8")
        for name in GUIDES:
            with self.subTest(guide=name):self.assertIn(f"./{name}",index)

    def test_guides_are_educational_and_no_editorial_drafts(self):
        for name in GUIDES:
            with self.subTest(name=name):
                text=(ROOT/name).read_text(encoding="utf-8")
                self.assertTrue(text.startswith("# "))
                self.assertGreater(len(text),1400)
                self.assertIn("Moj Prop educational resource",text)
                self.assertIn("not investment advice",text)
                self.assertIn("utm_source=github",text)
                self.assertNotIn("Editorial checks before public use:",text)
                self.assertNotIn("Publication status: editorial draft",text)
                self.assertNotIn("**Editorial draft — not public.**",text)
                self.assertNotIn("mojtabarozegar11-ship-it/MojPlayWin-Gateway-Private",text)

    def test_relative_document_links_resolve_within_public_directory(self):
        for p in ROOT.glob("*.md"):
            for link in re.findall(r"\]\((\./[^)]+)\)",p.read_text(encoding="utf-8")):
                with self.subTest(page=p.name,link=link):
                    target=(p.parent/link.split("#",1)[0]).resolve()
                    self.assertTrue(target.is_relative_to(ROOT.resolve()))
                    self.assertTrue(target.is_file())

    def test_official_external_links_only_point_to_owner_domain(self):
        for p in ROOT.glob("*.md"):
            body=p.read_text(encoding="utf-8")
            for url in re.findall(r"\]\((https?://[^)]+)\)",body):
                with self.subTest(page=p.name,url=url):
                    self.assertTrue(url.startswith("https://mojplaywin.com/"))
                    self.assertIn("utm_source=github",url)

if __name__=="__main__":unittest.main()
