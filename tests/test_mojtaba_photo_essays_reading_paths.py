import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("photo_paths",ROOT/"scripts/mojtaba_photo_essays_reading_paths.py")
m=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

def sample_home():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<div id="mpw-new-originals-20261015-b">Original gallery</div>
<div id="mpw-fifty-editorials-20261015">Fifty editorials</div>
<div id="mpw-academic-profile-20261016">Academic profile</div>
<div id="mpw-personal-expanded-20261016">Extended biography</div>
<div id="mpw-journal-longform-index-20261016">Earlier research</div>
<div id="mpw-journal-advanced-index-20261016">Advanced articles</div>
<div id="mpw-website-ten-index-20261016">Technical website articles</div>
<div id="mpw-vancouver-collab-photo-ten-20261016">Earlier portraits</div>
<div id="mpw-vancouver-enterprise-20-index-20261016">Enterprise series 1</div>
<div id="mpw-vancouver-enterprise-20-series2-index-20261016">Enterprise series 2</div>
<div id="mpw-mojtaba-twenty-image-essays-20261016">Current twenty essays and images</div>
<p>Preserve all prior paragraphs and owner photos.</p>
{% endblock %}"""

def sample_detail():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<h1>{{ item.title }}</h1>{{ item.content|linebreaks }}
""" + "\n".join('<figure id="mpw-mojtaba-essay-cover-20261016">Owner or generated image</figure>' for i in range(20))+"""
<aside id="mpw-journal-related-20261016">Earlier reading links</aside>
{% endblock %}
{% block title %}{{ item.title }} | Mojtaba Roozegar Journal{% endblock %}
{% block description %}{{ item.excerpt }}{% endblock %}"""

class TestReadingPathEnhancement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows,cls.old=m.rows_and_older(ROOT/"content")

    def test_original_twenty_plus_seventy_three_unchanged(self):
        self.assertEqual(len(self.rows),20)
        self.assertEqual(len(self.old),73)
        self.assertEqual(len(set(self.old)),73)
        self.assertEqual({p for _,numbers,_ in m.GROUPS for p in numbers},set(range(1,21)))
        self.assertEqual(set(m.TEMPLATES),{"home","posts","detail"})

    def test_all_twenty_visible_in_reading_sections(self):
        s=m.reading_section(self.rows)
        self.assertEqual(s.count('href="/mojtaba.roozegar/blog/'),20)
        self.assertEqual(s.count('<ol '),4)
        self.assertIn(m.HOMEBLOCK,s)
        for row in self.rows.values():
            self.assertIn(m.article_url(row),s)
        self.assertIn("explore",s.lower())
        self.assertNotIn("signed contract",s.lower())

    def test_twenty_detail_recommendations_and_collaboration_profile(self):
        s=m.detail_section(self.rows)
        self.assertEqual(s.count("item.slug =="),20)
        self.assertEqual(s.count(m.DETAILBLOCK),20)
        self.assertEqual(s.count('href="/mojtaba.roozegar/"'),20)
        for row in self.rows.values():
            self.assertIn('item.slug == "'+row["slug"]+'"',s)

    def test_additive_home_and_blog_protection(self):
        initial=sample_home()
        for name in ("home","posts"):
            changed=m.patch(name,initial,self.rows)
            self.assertEqual(changed.count(m.HOMEBLOCK),1)
            self.assertEqual(changed.count(m.DETAILBLOCK),0)
            self.assertIn("Preserve all prior paragraphs and owner photos.",changed)
            self.assertTrue(changed.startswith(initial.split("{% endblock %}")[0]))
            for marker in m.PROTECTED:self.assertEqual(changed.count(marker),1)
            with self.assertRaises(ValueError):m.patch(name,changed,self.rows)

    def test_original_photo_figures_and_seo_untouched(self):
        initial=sample_detail()
        changed=m.patch("detail",initial,self.rows)
        self.assertEqual(changed.count('id="mpw-mojtaba-essay-cover-20261016"'),20)
        self.assertEqual(changed.count(m.DETAILBLOCK),20)
        self.assertIn("{% block title %}{{ item.title }} | Mojtaba Roozegar Journal",changed)
        self.assertIn("{% block description %}{{ item.excerpt }}",changed)
        self.assertIn("Earlier reading links",changed)
        with self.assertRaises(ValueError):m.patch("detail",changed,self.rows)

    def test_missing_previous_section_fails_before_mutation(self):
        initial=sample_home()
        for marker in m.PROTECTED:
            with self.subTest(marker=marker):
                with self.assertRaises(ValueError):m.patch("home",initial.replace(marker,"missing"),self.rows)

    def test_never_manipulate_old_posts_or_photo_files(self):
        script=(ROOT/"scripts/mojtaba_photo_essays_reading_paths.py").read_text()
        self.assertNotIn("Post.objects.create(",script)
        self.assertNotIn("Post.objects.filter(slug__in=old).delete",script)
        self.assertNotIn("collectstatic",script)
        self.assertNotIn("jsonld",script.lower())

if __name__=="__main__":unittest.main()
