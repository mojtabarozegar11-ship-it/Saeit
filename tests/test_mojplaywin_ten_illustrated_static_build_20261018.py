import json,unittest,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from mojplaywin_ten_illustrated_static_build_20261018 import DATA,EXCLUDE,render,articles,guard,slug,MAX_BYTES

class MojPlayWinTenIllustratedPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=json.loads(DATA.read_text("utf-8"))
    def test_21_root_brand_areas_and_10_distinct_topics_each(self):
        self.assertEqual(len(self.data["pages"]),21)
        for path,info in self.data["pages"].items():
            self.assertEqual(len(info["items"]),10,path)
            self.assertEqual(len({x["title"] for x in info["items"]}),10,path)
            self.assertGreaterEqual(len(info["images"]),9,path)
    def test_exact_19_readable_routes_for_content_snapshot(self):
        self.assertEqual(len(self.data["pages"].keys()-EXCLUDE),19)
        self.assertEqual(EXCLUDE,{"/","/store/"})
    def test_unique_page_prefix_and_10_webp_sources(self):
        for path in self.data["pages"].keys()-EXCLUDE:
            section=articles(self.data,path)
            self.assertEqual(section.count('class="mpw-ten-card"'),10,path)
            self.assertEqual(section.count('loading="lazy"'),10,path)
            self.assertEqual(section.count(".webp"),10,path)
            self.assertEqual(section.count('alt="'),10,path)
            self.assertEqual(section.count('width="420" height="236"'),10,path)
            self.assertIn('id="mpw-ten-illustrated-20261018"',section)
    def test_preserves_every_existing_page_character(self):
        old='<!doctype html><html><head><title>Original title</title></head><body><main><p id="old">Original user-facing content</p></main><footer>Payments and products unchanged</footer></body></html>'
        old=old.replace('</main>', '<p>This historic introduction includes the original research context, citations, policies, responsibilities and related opportunities; it must stay fully intact in the published output.</p>'*2+'</main>')
        html=render(old,self.data,"/research/")
        self.assertIn('<title>Original title</title>',html)
        self.assertIn('<p id="old">Original user-facing content</p>',html)
        self.assertIn('<footer>Payments and products unchanged</footer>',html)
        self.assertIn('mpw-ten-illustrated-style-20261018',html)
        self.assertEqual(html.count('class="mpw-ten-card"'),10)
    def test_decline_forms_duplicate_and_payment_pages(self):
        for source in (
          '<!doctype html><head></head><main><form method="post"></form></main>',
          '<!doctype html><head></head><main><button type="submit">Buy</button></main>',
          '<!doctype html><head></head><main>payment_gateway iframe</main>',
          '<!doctype html><head></head><main><section id="mpw-ten-illustrated-20261018"></section></main>',
          '<!doctype html><head></head><p>No main</p>',
        ):
            with self.assertRaises(ValueError):
                guard(source,"/research/")
if __name__=="__main__":unittest.main()
