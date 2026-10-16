import importlib.util
import hashlib
import json
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("five",ROOT/"scripts/mojtaba_five_smart_web_portraits_publish.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fake_main():
    return """{% extends 'personal_site/base.html' %}
{% load static %}
{% block content %}
"""+"\n".join("<section "+marker+">Protected historic text and media</section>" for marker in m.KEEP)+"""
<div id="mpw-primary-personal-profile-20261016">Selected primary real user portrait</div>
"""+"\n".join('<figure data-mpw-diverse-collab-photo="20261016">Distinct prior collaboration image</figure>' for i in range(6))+"""
<p>Original user content remains entirely unchanged.</p>
{% endblock %}"""

def fake_detail():
    return """{% extends 'personal_site/base.html' %}
{% load static %}
{% block content %}
<h1>{{ item.title }}</h1>
{{ item.content|linebreaks }}
"""+"\n".join('<figure id="mpw-mojtaba-essay-cover-20261016">Previous 20 owner and generated original images</figure>' for _ in range(20))+"\n".join('<aside id="mpw-photoessay-related-20261016">Previous related reading</aside>' for _ in range(20))+"\n".join('<aside id="mpw-enterprise-collaboration-contact-20261016">Previous inquiry</aside>' for _ in range(20))+"""
{% endblock %}
{% block title %}{{ item.title }}{% endblock %}
{% block description %}{{ item.excerpt }}{% endblock %}"""

class FiveSmartWebPhotos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=m.article_data(ROOT)
        cls.images=m.verify_zip(ROOT)
        cls.old,cls.illustrated=m.original_slugs(ROOT,cls.rows)

    def test_five_distinct_images_and_93_unmodified_articles(self):
        self.assertEqual(len(self.rows),5)
        self.assertEqual(len(self.images),5)
        self.assertEqual(len(self.old),73)
        self.assertEqual(len(self.illustrated),20)
        self.assertEqual(len({r["slug"] for r in self.rows}),5)
        self.assertEqual(len({pic[2] for pic in self.images}),5)
        self.assertTrue(all(len(" ".join(x["paragraphs"]).split())>=160 for x in self.rows))

    def test_binary_photo_archive_source_digest_and_webp_bodies(self):
        p=ROOT/"assets"/m.ARCHIVE
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),m.ARCHIVE_HASH)
        with zipfile.ZipFile(p) as z:
            self.assertEqual(len(z.namelist()),6)
            for r in self.rows:
                b=z.read(r["image"])
                self.assertEqual(b[:4],b"RIFF")
                self.assertEqual(b[8:12],b"WEBP")

    def test_new_gallery_is_nonrepeating_and_has_correct_links(self):
        s=m.home_block(self.rows)
        self.assertEqual(s.count("Read the illustrated technical analysis"),5)
        self.assertEqual(s.count("<img "),5)
        self.assertEqual(s.count('<figure '),5)
        for r in self.rows:
            self.assertIn(r["image"],s)
            self.assertIn("/mojtaba.roozegar/blog/"+r["slug"]+"/",s)
        self.assertIn(m.MARK,s)

    def test_existing_home_and_blog_never_lost(self):
        s=fake_main()
        after=m.patch("home",s,self.rows)
        self.assertEqual(after.count(m.MARK),1)
        self.assertEqual(after.count('data-mpw-diverse-collab-photo="20261016"'),6)
        self.assertEqual(after.count('id="mpw-primary-personal-profile-20261016"'),1)
        self.assertIn("Original user content remains entirely unchanged.",after)
        for mark in m.KEEP:self.assertEqual(after.count(mark),1)
        with self.assertRaises(ValueError):m.patch("home",after,self.rows)
        posts=m.patch("posts",s.replace('id="mpw-primary-personal-profile-20261016"','id="not-home-primary-photo"'),self.rows)
        self.assertEqual(posts.count(m.MARK),1)

    def test_matching_single_detail_image_per_existing_article(self):
        after=m.patch("detail",fake_detail(),self.rows)
        self.assertEqual(after.count(m.DETAIL_MARK),5)
        self.assertEqual(after.count("item.slug =="),5)
        self.assertEqual(after.count('id="mpw-mojtaba-essay-cover-20261016"'),20)
        self.assertEqual(after.count('id="mpw-photoessay-related-20261016"'),20)
        self.assertEqual(after.count('id="mpw-enterprise-collaboration-contact-20261016"'),20)
        self.assertIn("{{ item.content|linebreaks }}",after)
        self.assertIn("{% block title %}{{ item.title }}",after)
        for row in self.rows:
            self.assertIn(row["title"],after)

    def test_missing_old_section_fails_closed(self):
        s=fake_main()
        for mark in m.KEEP:
            with self.subTest(mark=mark):
                with self.assertRaises(ValueError):m.patch("home",s.replace(mark,"missing"),self.rows)

    def test_scoped_to_personal_app_no_db_or_contact_rewrites(self):
        src=(ROOT/"scripts/mojtaba_five_smart_web_portraits_publish.py").read_text()
        self.assertEqual(set(m.TEMPLATES),{"home","posts","detail"})
        self.assertNotIn("Post.objects.create(",src)
        self.assertNotIn("Post.objects.update(",src)
        self.assertNotIn("contact.html",src)
        self.assertNotIn("payment",m.ASSET.lower())
if __name__=="__main__":unittest.main()
