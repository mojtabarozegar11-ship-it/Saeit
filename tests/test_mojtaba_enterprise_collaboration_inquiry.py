import importlib.util
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("inquiry",ROOT/"scripts/mojtaba_enterprise_collaboration_inquiry.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def home():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<div id="mpw-new-originals-20261015-b">Original gallery</div>
<div id="mpw-fifty-editorials-20261015">Fifty entries</div>
<div id="mpw-academic-profile-20261016">Academic profile</div>
<div id="mpw-personal-expanded-20261016">Thirty-two sections</div>
<div id="mpw-journal-longform-index-20261016">Seven articles</div>
<div id="mpw-journal-advanced-index-20261016">Six articles</div>
<div id="mpw-website-ten-index-20261016">Ten website studies</div>
<div id="mpw-vancouver-collab-photo-ten-20261016">Ten Vancouver studies</div>
<div id="mpw-vancouver-enterprise-20-index-20261016">First enterprise twenty</div>
<div id="mpw-vancouver-enterprise-20-series2-index-20261016">Second enterprise twenty</div>
<div id="mpw-mojtaba-twenty-image-essays-20261016">Current illustrated 20</div>
<div id="mpw-photoessay-reading-guides-20261016">New reading paths</div>
<p>Never change existing editorial content, photos or biographies.</p>
{% endblock %}"""
def detail():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<h1>{{ item.title }}</h1>{{ item.content|linebreaks }}
"""+"\n".join('<figure id="mpw-mojtaba-essay-cover-20261016">Original photo</figure>' for _ in range(20))+"\n".join('<aside id="mpw-photoessay-related-20261016">Related article navigation</aside>' for _ in range(20))+"""
<aside id="mpw-journal-related-20261016">Earlier research reading</aside>
{% endblock %}
{% block title %}{{ item.title }} | Mojtaba Roozegar Journal{% endblock %}
{% block description %}{{ item.excerpt }}{% endblock %}"""
class CollaborationInquiryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.new,cls.old=m.photo_rows(ROOT/"content")
    def test_count_and_safe_scope(self):
        self.assertEqual(len(self.new),20)
        self.assertEqual(len(self.old),73)
        self.assertEqual(set(m.TEMPLATES),{"home","posts","detail"})
        self.assertEqual(m.CONTACT,"/mojtaba.roozegar/contact/")
    def test_six_distinct_project_offers_with_evidence(self):
        self.assertEqual(len(m.OFFERS),6)
        self.assertEqual(len({x[0] for x in m.OFFERS}),6)
        self.assertEqual(len({x[3] for x in m.OFFERS}),6)
        s=m.card_section()
        self.assertEqual(s.count("Read the relevant technical article"),6)
        self.assertIn("Send a collaboration inquiry",s)
        self.assertIn(m.CONTACT,s)
        self.assertIn("not completed client contracts",s)
    def test_additive_home_and_journal(self):
        for page in ("home","posts"):
            updated=m.patch(page,home(),self.new)
            self.assertEqual(updated.count(m.MARK),1)
            self.assertIn("Never change existing editorial",updated)
            for marker in m.PROTECTED:self.assertEqual(updated.count(marker),1)
            with self.assertRaises(ValueError):m.patch(page,updated,self.new)
    def test_twenty_detail_ctas_only_and_unchanged_seo(self):
        changed=m.patch("detail",detail(),self.new)
        self.assertEqual(changed.count(m.DETAIL_MARK),20)
        self.assertEqual(changed.count("item.slug =="),20)
        self.assertIn("{{ item.content|linebreaks }}",changed)
        self.assertIn("{% block title %}{{ item.title }}",changed)
        self.assertIn("{% block description %}{{ item.excerpt }}",changed)
        self.assertEqual(changed.count('id="mpw-mojtaba-essay-cover-20261016"'),20)
        with self.assertRaises(ValueError):m.patch("detail",changed,self.new)
    def test_missing_previous_guide_rejected(self):
        for marker in m.PROTECTED:
            with self.subTest(marker=marker):
                with self.assertRaises(ValueError):m.patch("home",home().replace(marker,"missing"),self.new)
    def test_no_contact_form_db_or_media_code_mutation(self):
        script=(ROOT/"scripts/mojtaba_enterprise_collaboration_inquiry.py").read_text()
        self.assertNotIn("Post.objects.create(",script)
        self.assertNotIn("collectstatic",script)
        self.assertNotIn("contact.html",script)
        self.assertNotIn("EMAIL_HOST",script)
if __name__=="__main__":unittest.main()
