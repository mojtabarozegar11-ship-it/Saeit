import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/mojtaba_ten_website_articles_publish.py"
DOC=ROOT/"content/mojtaba_ten_advanced_website_engineering_20261016.json"
spec=importlib.util.spec_from_file_location("webengineer",SCRIPT)
web=importlib.util.module_from_spec(spec)
spec.loader.exec_module(web)

def preserved_template():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<div id="mpw-new-originals-20261015-b">Owner photos</div>
<div id="mpw-fifty-editorials-20261015">Fifty older editorials</div>
<div id="mpw-academic-profile-20261016">UPM biography</div>
<div id="mpw-personal-expanded-20261016">Thirty-two expansions</div>
<div id="mpw-journal-longform-index-20261016">Seven native posts</div>
<div id="mpw-journal-advanced-index-20261016">Six advanced native posts</div>
<p>Do not replace old articles, pictures, or site design.</p>
{% endblock %}"""

class TenExpertWebsiteArticleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=web.load_manifest(DOC)

    def test_exactly_ten_deep_original_technical_articles(self):
        posts=self.data["articles"]
        self.assertEqual(len(posts),10)
        self.assertEqual(len({p["slug"] for p in posts}),10)
        self.assertEqual(len({p["title"] for p in posts}),10)
        self.assertTrue(all(len(p["content"].split())>=600 for p in posts))
        self.assertGreater(sum(len(p["content"].split()) for p in posts),6300)
        joined=" ".join(p["content"].lower() for p in posts)
        for topic in ("django","postgre","accessib","core web vitals","owasp","canonical","rollback","idempotency","observability"):
            self.assertIn(topic,joined)

    def test_safe_home_and_blog_additive_install(self):
        for page in web.TEMPLATES:
            with self.subTest(page=page):
                original=preserved_template()
                out=web.patch_template(original,self.data)
                self.assertEqual(out.count(web.MARKER),1)
                for mark in web.PROTECTED:
                    self.assertEqual(out.count(mark),1)
                self.assertIn("Do not replace old articles",out)
                self.assertEqual(out.count("href="),10)
                with self.assertRaises(ValueError):
                    web.patch_template(out,self.data)

    def test_each_new_article_has_permalink_and_readable_summary(self):
        block=web.index_block(self.data)
        for x in self.data["articles"]:
            self.assertIn("/mojtaba.roozegar/blog/"+x["slug"]+"/",block)
            self.assertIn(x["title"],block)
        self.assertIn("Ten Expert Articles",block)
        self.assertIn("mpw-website-ten-index-20261016",block)

    def test_missing_protected_material_blocks_deploy(self):
        for mark in web.PROTECTED:
            with self.subTest(mark=mark):
                with self.assertRaises(ValueError):
                    web.patch_template(preserved_template().replace(mark,"missing"),self.data)

    def test_unsafe_manifest_cannot_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"bad.json"
            doc=json.loads(DOC.read_text(encoding="utf-8"))
            doc["articles"][0]["slug"]=doc["articles"][1]["slug"]
            path.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):web.load_manifest(path)
            doc["articles"][0]["slug"]="unique-ten-web-engineer-slug"
            doc["articles"][0]["content"]="insufficient"
            path.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):web.load_manifest(path)

    def test_scope_is_exactly_two_existing_personal_templates(self):
        self.assertEqual(web.TEMPLATES,{"home":"home.html","posts":"posts.html"})

if __name__=="__main__":
    unittest.main()
