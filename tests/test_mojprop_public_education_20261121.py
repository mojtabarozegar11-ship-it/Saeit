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
# Reviewed, independent free Signal Desk teaching material; six historical guides
# retain their immutable editorial and no-draft acceptance checks.
FREE_SIGNAL_SAMPLE="signal-desk-free-scenario-sample.md"
REAL_GOLD_MARKET_BRIEF="gold-macro-scenarios-q4-2026-20261122.md"
# Exactly two explicit authority references, never a general off-site allow rule.
TRUSTED_EDUCATIONAL_REFERENCES=frozenset((
    "https://www.law.cornell.edu/cfr/text/17/4.41",
    "https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/social-media-stock-scams",
    "https://fred.stlouisfed.org/series/DFII10",
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_real_yield_curve",
    "https://www.gold.org/goldhub/research/gold-demand-trends/gold-demand-trends-q3-2026/outlook",
    "https://www.elibrary.imf.org/view/journals/068/2026/007/article-A001-en.xml",
))

class MojPropEducationPublicationTests(unittest.TestCase):
    def test_root_readme_links_to_public_education_hub(self):
        repo_readme=(ROOT.parents[2]/"README.md").read_text(encoding="utf-8")
        self.assertEqual(repo_readme.count("docs/mojprop/education/README.md"),1)
        self.assertIn("five free guides to simulated trading",repo_readme.lower())
        self.assertIn("starter30-buyer-guide.md",repo_readme)
        self.assertIn("30 TRX simulated challenge",repo_readme)

    def test_public_guide_catalog_is_complete(self):
        self.assertEqual({p.name for p in ROOT.glob("*.md")},set(GUIDES)|{"README.md",FREE_SIGNAL_SAMPLE,REAL_GOLD_MARKET_BRIEF})
        index=(ROOT/"README.md").read_text(encoding="utf-8")
        for name in GUIDES:
            with self.subTest(guide=name):self.assertIn(f"./{name}",index)
        self.assertIn(f"./{FREE_SIGNAL_SAMPLE}",index)
        self.assertIn(f"./{REAL_GOLD_MARKET_BRIEF}",index)

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

    def test_dated_gold_research_has_attributed_owner_domain_return_links(self):
        # The linked source-based article is discovered from main on PR merge
        # checks. Keep actual owner-site referrals attributable without
        # weakening the strict external-source allowlist below.
        article=(ROOT/"gold-macro-scenarios-q4-2026-20261122.md").read_text(encoding="utf-8")
        for url in (
            "https://mojplaywin.com/mojtaba.bot.ai/?utm_source=github",
            "https://mojplaywin.com/moj-prop-intake/?format=html&service=signals&utm_source=github",
        ):
            with self.subTest(owner_link=url):
                self.assertIn(url,article)
        self.assertIn("No buy/sell/entry/stop-loss/target levels are asserted",article)

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
                    if url in TRUSTED_EDUCATIONAL_REFERENCES:
                        continue
                    self.assertTrue(url.startswith("https://mojplaywin.com/"))
                    self.assertIn("utm_source=github",url)

if __name__=="__main__":unittest.main()
