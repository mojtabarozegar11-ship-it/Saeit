"""Public Persian education SVGs and isolated homepage additive injection, offline regression."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import os
import tempfile
import unittest
from xml.etree import ElementTree
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
NAME="mojtaba_four_course_posters_home_20261028"
SPEC=importlib.util.spec_from_file_location(NAME,ROOT/"scripts"/(NAME+".py"))
HOME=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOME)

try:
    import django
    from django.conf import settings
    if not settings.configured:
        settings.configure(SECRET_KEY="fixture-only-not-live",ALLOWED_HOSTS=["testserver"],
            ROOT_URLCONF="social_hub.urls",INSTALLED_APPS=[],USE_I18N=True)
    django.setup()
    from django.test import RequestFactory
    from social_hub.course_showcase import COURSES,BY_SLUG,svg_for,poster,gallery,ID
    DJANGO_AVAILABLE=True
except ImportError:
    DJANGO_AVAILABLE=False

class OriginalPostersTests(unittest.TestCase):
    @unittest.skipUnless(DJANGO_AVAILABLE,"Django not installed in offline test runner")
    def test_all_four_svg_posters_are_real_parseable_vector_images(self):
        self.assertEqual(len(COURSES),4)
        self.assertEqual(len({x["slug"] for x in COURSES}),4)
        for c in COURSES:
            with self.subTest(slug=c["slug"]):
                xml=svg_for(c["slug"])
                tree=ElementTree.fromstring(xml)
                self.assertTrue(tree.tag.endswith("svg"))
                self.assertEqual(tree.attrib["width"],"900")
                self.assertEqual(tree.attrib["height"],"1200")
                self.assertIn("1200",tree.attrib["viewBox"])
                self.assertIn(c["lines"][0],xml)
                self.assertIn(c["lines"][1],xml)
                self.assertNotIn("<script",xml.lower())
                self.assertNotIn("javascript:",xml.lower())
                self.assertNotIn("data:image",xml.lower())
                self.assertNotIn("dr.mojtaba.rozegar",xml)
                self.assertNotIn("<image ",xml)
                self.assertLess(len(xml.encode("utf-8")),40_000)
                result=poster(RequestFactory().get("/poster/"+c["slug"]),c["slug"])
                self.assertEqual(result.status_code,200)
                self.assertTrue(result["Content-Type"].startswith("image/svg+xml"))
                self.assertIn("sandbox",result["Content-Security-Policy"])
        self.assertEqual(poster(RequestFactory().get("/nope"),"fake").status_code,404)

    @unittest.skipUnless(DJANGO_AVAILABLE,"Django not installed in offline test runner")
    def test_html_has_four_distinct_posters_details_without_fake_buy_buttons(self):
        resp=gallery(RequestFactory().get("/courses/"))
        html=resp.content.decode("utf-8")
        self.assertEqual(resp.status_code,200)
        self.assertIn('lang="fa" dir="rtl"',html)
        self.assertIn("width=device-width",html)
        self.assertIn("ثبت‌نام و پرداخت در این صفحه فعال نیست",html)
        self.assertIn("هیچ تضمین درآمدی",html)
        self.assertNotIn("dr.mojtaba.rozegar",html)
        self.assertNotIn("پرداخت آنلاین",html)
        self.assertEqual(html.count('<article class="mpw-course-card"'),4)
        for c in COURSES:
            self.assertIn(c["title"],html)
            self.assertIn('/posters/'+c["slug"]+'.svg',html)
            self.assertIn('id="'+c["slug"]+'"',html)
        self.assertIn("/mojtaba.roozegar/contact/",html)

class HomepageInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=Path(self.temp.name)/"personal"
        self.target=self.app/HOME.TEMPLATE
        self.target.parent.mkdir(parents=True)
        (self.app/"manage.py").write_text("# local test",encoding="utf-8")
        self.original=(
            '{% extends "personal_site/base.html" %}\n'
            '{% block content %}\n'
            '<section id="existing-biography"><h1>Existing biography</h1></section>\n'
            '<section id="existing-research">Research</section>\n'
            '{% endblock %}\n'
        )
        self.target.write_text(self.original,encoding="utf-8")
        self.bak=Path(self.temp.name)/"backups"
        self.prev=os.environ.get("MPW_COURSE_POSTERS_TEST")
        os.environ["MPW_COURSE_POSTERS_TEST"]="1"

    def tearDown(self):
        if self.prev is None:os.environ.pop("MPW_COURSE_POSTERS_TEST",None)
        else:os.environ["MPW_COURSE_POSTERS_TEST"]=self.prev
        self.temp.cleanup()

    @unittest.skipUnless(DJANGO_AVAILABLE,"Django unavailable")
    def test_public_page_marker_matches_reversible_home_installer_exactly(self):
        self.assertEqual(ID,HOME.MARKER.split('"')[1])
        content=HOME.patch(self.original)
        self.assertEqual(content.count('<section id="'+ID+'"'),1)

    def test_home_adds_four_with_no_existing_markup_removed_and_rolls_back(self):
        report=HOME.check(self.app)
        self.assertEqual(report["posters"],4)
        new=HOME.patch(self.original)
        self.assertEqual(new.count(HOME.MARKER),1)
        self.assertIn("existing-biography",new)
        self.assertIn("existing-research",new)
        self.assertTrue(new.startswith(self.original[:self.original.index("{% endblock %}")]))
        for slug,_,_ in HOME.POSTERS:
            self.assertEqual(new.count("/posters/"+slug+".svg"),1)
            self.assertIn("/courses/#"+slug,new)
        done=HOME.install(self.app,self.bak,"123456789")
        self.assertEqual(done["status"],"installed")
        self.assertEqual(self.target.read_text(),new)
        with self.assertRaises(RuntimeError):HOME.check(self.app)
        with self.assertRaises(RuntimeError):HOME.install(self.app,self.bak,"123456790")
        rolled=HOME.rollback(self.app,self.bak,"123456789")
        self.assertEqual(rolled["status"],"restored")
        self.assertEqual(self.target.read_text(),self.original)

    def test_existing_section_duplicate_or_modified_home_refuses_overwrite(self):
        old=self.original.replace("{% block content %}","")
        with self.assertRaises(RuntimeError):HOME.patch(old)
        self.target.write_text(self.original+HOME.MARKER)
        with self.assertRaises(RuntimeError):HOME.patch(self.target.read_text())
        self.target.write_text(self.original)
        HOME.install(self.app,self.bak,"123456799")
        self.target.write_text(self.target.read_text()+"\n<!-- legitimate later edit -->")
        with self.assertRaises(RuntimeError):HOME.rollback(self.app,self.bak,"123456799")

    def test_nonapproved_root_rejected_outside_test_mode(self):
        os.environ.pop("MPW_COURSE_POSTERS_TEST",None)
        with self.assertRaises(RuntimeError):HOME.check(self.app)

if __name__=="__main__":
    unittest.main()
