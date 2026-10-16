import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("enterprise20",ROOT/"scripts/mojtaba_vancouver_enterprise_web20_publish.py")
publisher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)
CONTENTS=ROOT/"content"

def example_template():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<div id="mpw-new-originals-20261015-b">Owner gallery</div>
<div id="mpw-fifty-editorials-20261015">Original editorial archive</div>
<div id="mpw-academic-profile-20261016">Academic profile</div>
<div id="mpw-personal-expanded-20261016">Personal portfolio</div>
<div id="mpw-journal-longform-index-20261016">Seven originals</div>
<div id="mpw-journal-advanced-index-20261016">Six advanced articles</div>
<div id="mpw-website-ten-index-20261016">Ten engineering articles</div>
<div id="mpw-vancouver-collab-photo-ten-20261016">Ten photo-backed Vancouver pieces</div>
<p>Preserve the original live website, template and twenty photographs.</p>
{% endblock %}"""

class TestVancouverIndustrialEnterprise20(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=publisher.load_articles(CONTENTS)

    def test_twenty_distinct_high_value_proposals(self):
        rows=self.rows
        self.assertEqual(len(rows),20)
        self.assertEqual(len({x["slug"] for x in rows}),20)
        self.assertEqual(len({x["title"] for x in rows}),20)
        self.assertTrue(all(len(x["content"].split())>=330 for x in rows))
        self.assertGreater(sum(len(x["content"].split()) for x in rows),7000)
        blob=" ".join(x["content"].lower() for x in rows)
        for word in ("vancouver","industrial","enterprise","security","procurement","manufacturing","pilot","artificial intelligence"):
            self.assertIn(word,blob)

    def test_twenty_original_valid_accessible_vector_images(self):
        for i,article in enumerate(self.rows,1):
            with self.subTest(slug=article["slug"]):
                b=publisher.svg_diagram(article,i)
                root=ET.fromstring(b)
                self.assertEqual(root.attrib["viewBox"],"0 0 1200 675")
                self.assertIn(article["title"].encode()[:15],b)
                self.assertNotIn(b"<script",b)
                self.assertNotIn(b"<foreignObject",b)
                self.assertIn(b"<title ",b)
                for label in article["diagram"]:
                    self.assertIn(label.encode(),b)
                self.assertTrue(publisher.image_name(article["slug"]).endswith(article["slug"]+".svg"))

    def test_home_and_blog_index_addition_preserves_previous_content(self):
        for key in ("home","posts"):
            out=publisher.patch(key,example_template(),self.rows)
            self.assertEqual(out.count(publisher.INDEX_MARK),1)
            for mark in publisher.PROTECTED:
                self.assertEqual(out.count(mark),1)
            self.assertIn("Preserve the original live website",out)
            self.assertEqual(out.count("<article"),20)
            self.assertEqual(out.count("{% static 'personal_site/enterprise_web_diagrams_20261016/"),20)
            with self.assertRaises(ValueError):publisher.patch(key,out,self.rows)

    def test_detail_only_for_matching_native_article(self):
        original="""{% extends 'personal_site/base.html' %}
{% block content %}
<h1>{{ item.title }}</h1><article>{{ item.content|linebreaks }}</article>
{% endblock %}"""
        out=publisher.patch("detail",original,self.rows)
        self.assertEqual(out.count(publisher.DETAIL_MARK),20)
        self.assertIn('kind == "Article"',out)
        self.assertEqual(out.count("item.slug =="),20)
        self.assertIn("{{ item.content|linebreaks }}",out)
        with self.assertRaises(ValueError):publisher.patch("detail",out,self.rows)

    def test_protection_rejects_missing_old_content(self):
        for mark in publisher.PROTECTED:
            with self.subTest(marker=mark):
                with self.assertRaises(ValueError):
                    publisher.patch("home",example_template().replace(mark,"missing"),self.rows)

    def test_content_safety_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for i in (1,2,3,4):
                path=CONTENTS/("mojtaba_vancouver_enterprise_web_part_"+str(i)+"_20261016.json")
                (p/path.name).write_bytes(path.read_bytes())
            file=p/"mojtaba_vancouver_enterprise_web_part_4_20261016.json"
            d=json.loads(file.read_text())
            d["articles"][0]["slug"]=self.rows[0]["slug"]
            file.write_text(json.dumps(d))
            with self.assertRaises(ValueError):publisher.load_articles(p)

    def test_scope_and_previous_thirty_three(self):
        self.assertEqual(set(publisher.TEMPLATES),{"home","posts","detail"})
        self.assertEqual(len(publisher.OLD_FILES),5)
        self.assertEqual(publisher.STATIC_FOLDER,"personal_site/enterprise_web_diagrams_20261016")
        older=publisher.load_older(CONTENTS)
        self.assertEqual(len(older),33)

if __name__=="__main__":
    unittest.main()
