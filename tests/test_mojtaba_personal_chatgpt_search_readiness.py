"""Pure tests; no network required for OpenAI bot readiness checks."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "personal_chatgpt_readiness",
    ROOT / "scripts/mojtaba_personal_chatgpt_search_readiness.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

class ChatGPTReadinessTests(unittest.TestCase):
    def test_root_robot_allows_oai_searchbot(self):
        robots = b"User-agent: *\nAllow: /\nDisallow: /admin/\n"
        parsed = mod.parse_policy(robots)
        self.assertTrue(all(parsed["oai_searchbot"].values()))
        self.assertTrue(all(parsed["chatgpt_user"].values()))

    def test_root_bot_specific_disallow_overrides_star(self):
        robots = b"User-agent: *\nAllow: /\nUser-agent: OAI-SearchBot\nDisallow: /\n"
        parsed = mod.parse_policy(robots)
        self.assertFalse(all(parsed["oai_searchbot"].values()))

    def test_training_bot_independent_of_searchbot(self):
        robots = (b"User-agent: GPTBot\nDisallow: /\n"
                  b"User-agent: OAI-SearchBot\nAllow: /\n")
        parsed = mod.parse_policy(robots)
        self.assertFalse(all(parsed["gptbot_training"].values()))
        self.assertTrue(all(parsed["oai_searchbot"].values()))

    def test_bilingual_faq_and_person_metadata(self):
        obj = {"@context": "https://schema.org", "@type": "ProfilePage",
               "mainEntity": {"@type": "Person", "name": "Mojtaba Roozegar",
                              "alternateName": "مجتبی روزگار",
                              "sameAs": ["https://example.com/profile"]}}
        page = ('<html><head><title>Mojtaba Roozegar | Official Website</title>'
                '<meta name="robots" content="index,follow">'
                f'<link rel="canonical" href="{mod.PERSONAL}about/">'
                '<script type="application/ld+json">'+json.dumps(obj)+
                '</script></head><body>'+mod.FAQ_MARKER+
                ' Who is Mojtaba Roozegar? مجتبی روزگار کیست؟</body></html>').encode()
        s = mod.summarize_page(page, mod.PERSONAL+"about/")
        self.assertTrue(s["canonical_matches"])
        self.assertTrue(s["person_jsonld"])
        self.assertTrue(s["faq_english_question_present"])
        self.assertTrue(s["faq_persian_question_present"])

    def test_noindex_detectable(self):
        doc = (f'<meta name="robots" content="noindex"><link rel="canonical" '
               f'href="{mod.PERSONAL}">').encode()
        s = mod.summarize_page(doc, mod.PERSONAL)
        self.assertIn("noindex", s["robots"])

    def test_sitemap_counts_article_routes(self):
        urls = [mod.PERSONAL, mod.PERSONAL+"about/"] + [
            mod.PERSONAL+"blog/topic-"+str(i)+"/" for i in range(93)]
        xml = ("<urlset>"+ "".join("<url><loc>"+u+"</loc></url>" for u in urls)
               +"</urlset>").encode()
        s = mod.sitemap_summary(xml)
        self.assertEqual(s["blog_articles"], 93)
        self.assertEqual(s["total"], 95)
        self.assertTrue(s["home"])
        self.assertTrue(s["about"])

    def test_scope_never_targets_unrelated_root_page(self):
        self.assertTrue(mod.PERSONAL.startswith(mod.ROOT))
        self.assertEqual(mod.PATHS, ("", "about/", "blog/"))
        self.assertEqual(mod.ROBOTS, "https://mojplaywin.com/robots.txt")

if __name__ == "__main__":
    unittest.main()
