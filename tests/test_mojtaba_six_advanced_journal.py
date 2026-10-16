import importlib.util
import html
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/mojtaba_six_advanced_journal_publish.py"
DOC=ROOT/"content/mojtaba_six_advanced_journal_articles_20261016.json"
spec=importlib.util.spec_from_file_location("article_expand",SCRIPT)
publisher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)

def base_template():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<div id="mpw-new-originals-20261015-b">Original photos</div>
<div id="mpw-fifty-editorials-20261015">Earlier editorials</div>
<div id="mpw-academic-profile-20261016">Earlier biography</div>
<div id="mpw-personal-expanded-20261016">Earlier expanded copy</div>
<div id="mpw-journal-longform-index-20261016">Seven previous articles</div>
<p>Existing content not replaced.</p>
{% endblock %}"""

def detail_template():
    return """{% extends 'personal_site/base.html' %}
{% block title %}{{ item.title }}{% endblock %}
{% block content %}
<h1>{{ item.title }}</h1>
<p>{{ item.content|linebreaks }}</p>
{% endblock %}"""

class SixAdvancedJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=publisher.load_manifest(DOC)

    def test_six_unique_original_substantive_articles(self):
        items=self.doc["articles"]
        self.assertEqual(len(items),6)
        self.assertEqual(len({i["slug"] for i in items}),6)
        self.assertTrue(all(len(i["content"].split())>=500 for i in items))
        self.assertGreater(sum(len(i["content"].split()) for i in items),3300)

    def test_new_index_links_six_articles_with_no_old_content_loss(self):
        old=base_template()
        for page in ("home","posts"):
            new=publisher.patch_template(old,self.doc,page=page)
            self.assertIn("Existing content not replaced",new)
            self.assertEqual(new.count(publisher.MARKER),1)
            for oldmarker in publisher.PROTECTED:
                self.assertEqual(new.count(oldmarker),1)
            for row in self.doc["articles"]:
                self.assertIn("/blog/"+row["slug"]+"/",new)
            with self.assertRaises(ValueError):
                publisher.patch_template(new,self.doc,page=page)

    def test_seo_only_article_detail_and_related_links(self):
        out=publisher.patch_template(detail_template(),self.doc,page="detail")
        self.assertEqual(out.count(publisher.DETAIL_MARKER),1)
        self.assertIn("BlogPosting",out)
        self.assertIn("datePublished",out)
        self.assertIn("{% if kind == 'Article' %}",out)
        self.assertIn("{{ item.excerpt|truncatechars:155 }}",out)
        self.assertIn("{{ item.title }} | Mojtaba Roozegar Journal",out)
        self.assertIn("{{ item.content|linebreaks }}",out)
        self.assertIn("{{ item.title }}",out)
        self.assertNotIn("noindex",out.lower())
        for row in self.doc["articles"]:
            self.assertIn(row["slug"],out)

    def test_no_duplicate_title_or_description_blocks(self):
        o=publisher.patch_template(detail_template(),self.doc,page="detail")
        self.assertEqual(o.count("{% block title %}"),1)
        self.assertEqual(o.count("{% block description %}"),1)
        with self.assertRaises(ValueError):
            publisher.patch_template(o,self.doc,page="detail")

    def test_fail_closed_when_protected_sections_missing(self):
        for marker in publisher.PROTECTED:
            with self.subTest(marker=marker):
                with self.assertRaises(ValueError):
                    publisher.patch_template(base_template().replace(marker,"no-data"),self.doc,page="home")

    def test_schema_invalid_or_short_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            data=json.loads(DOC.read_text())
            data["articles"][0]["content"]="very short"
            f=Path(d)/"bad.json";f.write_text(json.dumps(data))
            with self.assertRaises(ValueError):publisher.load_manifest(f)
            data["articles"][0]["content"]=data["articles"][1]["content"]
            data["articles"][0]["slug"]=data["articles"][1]["slug"]
            f.write_text(json.dumps(data))
            with self.assertRaises(ValueError):publisher.load_manifest(f)

    def test_html_entity_normalization_for_live_article_text(self):
        raw=self.doc["articles"][-1]["content"].splitlines()[1][:50]
        self.assertIn("game's",raw)
        encoded=html.escape(raw)
        self.assertNotEqual(raw,encoded)
        self.assertIn(raw,html.unescape("<p>"+encoded+"</p>"))

    def test_allowlisted_three_templates_and_no_other_files(self):
        self.assertEqual(set(publisher.TEMPLATES),{"home","posts","detail"})

if __name__=="__main__":
    unittest.main()
