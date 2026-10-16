import importlib.util,json,html
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("vancouver",ROOT/"scripts/mojtaba_vancouver_photo_articles_safe_publish.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FILES=[ROOT/"content/mojtaba_vancouver_collab_part_a_20261016.json",ROOT/"content/mojtaba_vancouver_collab_part_b_20261016.json"]

def original():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<div id="mpw-new-originals-20261015-b">Photos</div>
<div id="mpw-fifty-editorials-20261015">Editorials</div>
<div id="mpw-academic-profile-20261016">Academic</div>
<div id="mpw-personal-expanded-20261016">Thirty-two sections</div>
<div id="mpw-journal-longform-index-20261016">Seven articles</div>
<div id="mpw-journal-advanced-index-20261016">Six articles</div>
<div id="mpw-website-ten-index-20261016">Ten web-engineering articles</div>
<p>The original site survives.</p>
{% endblock %}"""

class TestVancouverCollaborationImages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=m.load_bundle(FILES)

    def test_ten_unique_substantive_independent_articles(self):
        self.assertEqual(len(self.rows),10)
        self.assertEqual(len({r["slug"] for r in self.rows}),10)
        self.assertTrue(all(len(r["content"].split())>=300 for r in self.rows))
        self.assertGreater(sum(len(r["content"].split()) for r in self.rows),3250)
        self.assertEqual(len({r["photo_id"] for r in self.rows}),10)

    def test_original_photo_links_include_rightful_sources(self):
        block=m.index_html(self.rows,"/mojtaba.roozegar/media/")
        self.assertEqual(block.count('loading="lazy"'),10)
        self.assertEqual(block.count("Photograph:"),10)
        self.assertEqual(block.count('alt="'),10)
        for r in self.rows:
            self.assertIn(r["slug"]+".jpg",block)
            self.assertIn(r["title"],html.unescape(block))

    def test_additive_home_and_blog_preserves_all_prior_markers(self):
        for page in ("home","posts"):
            with self.subTest(page=page):
                out=m.patch(page,original(),self.rows,"/mojtaba.roozegar/media/")
                self.assertEqual(out.count(m.MARKER),1)
                self.assertIn("The original site survives.",out)
                for mark in m.PREVIOUS:
                    self.assertEqual(out.count(mark),1)
                with self.assertRaises(ValueError):m.patch(page,out,self.rows,"/mojtaba.roozegar/media/")

    def test_detail_only_inserts_photo_when_native_cover_missing(self):
        template="""{% extends 'personal_site/base.html' %}{% block content %}
        <h1>{{ item.title }}</h1><p>{{ item.content|linebreaks }}</p>{% endblock %}"""
        out=m.patch("detail",template,self.rows,"/media/")
        self.assertEqual(out.count(m.DETAIL_MARKER),1)
        self.assertIn("item.cover.url",out)
        self.assertIn('{% if kind == "Article" and item.cover %}',out)
        already=template.replace("<h1>","{% if item.cover %}<img src='{{ item.cover.url }}'>{% endif %}<h1>")
        self.assertEqual(m.patch("detail",already,self.rows,"/media/"),already)

    def test_fail_when_prior_article_blocks_missing(self):
        for mark in m.PREVIOUS:
            with self.subTest(mark=mark):
                with self.assertRaises(ValueError):
                    m.patch("home",original().replace(mark,"deleted"),self.rows,"/media/")

    def test_reject_slug_collision_and_short_article(self):
        with TemporaryDirectory() as tmp:
            a=json.loads(FILES[0].read_text());b=json.loads(FILES[1].read_text())
            p=Path(tmp)/"a.json";q=Path(tmp)/"b.json"
            a["articles"][0]["slug"]=b["articles"][0]["slug"]
            p.write_text(json.dumps(a));q.write_text(json.dumps(b))
            with self.assertRaises(ValueError):m.load_bundle([p,q])
            a["articles"][0]["slug"]="vancouver-testing-safe-new-unique-slug"
            a["articles"][0]["content"]="Too short"
            p.write_text(json.dumps(a))
            with self.assertRaises(ValueError):m.load_bundle([p,q])

    def test_existing_gallery_image_fallback_avoids_legacy_db_mutations(self):
        original='{% block content %}<h1>{{ item.title }}</h1>{% endblock %}'
        mapping={'prior-personal-article-test':'https://mojplaywin.com/mojtaba.roozegar/media/owner_gallery_20261015_b/example.jpg'}
        patched=m.legacy_photo_fallback(original,mapping)
        self.assertIn('mpw-vancouver-older-article-photo-20261016',patched)
        self.assertIn('owner_gallery_20261015_b/',patched)
        self.assertIn('not item.cover',patched)
        self.assertEqual(m.legacy_photo_fallback(original,{}),original)

    def test_strict_scope_and_media_name(self):
        self.assertEqual(set(m.TEMPLATES),{"home","posts","detail"})
        for row in self.rows:
            self.assertEqual(m.expected_path(row["slug"]),"posts/vancouver-collab-20261016/"+row["slug"]+".jpg")
        self.assertEqual(len(m.OLD_MANIFESTS),3)

if __name__=="__main__":unittest.main()
