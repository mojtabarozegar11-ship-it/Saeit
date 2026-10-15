import importlib.util
import pathlib
import unittest

path=pathlib.Path(__file__).resolve().parents[1]/"scripts/mojtaba_second_10_owner_photos.py"
spec=importlib.util.spec_from_file_location("owner_second",path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class SecondPhotoBatchTest(unittest.TestCase):
    def template(self):
        return """{% extends 'personal_site/base.html' %}
{% load static %}
{% block title %}Existing title{% endblock %}
{% block description %}Existing description{% endblock %}
{% block content %}
<div id="mpw-inner-content-20261015"><p>Preexisting English content</p></div>
{% endblock %}
"""
    def test_nine_pages_are_additive_and_do_not_remove_existing_material(self):
        self.assertEqual(len(m.ROUTES),9)
        for page in m.ROUTES:
            with self.subTest(page=page):
                before=self.template()
                after=m.patch(page,before)
                self.assertIn("Preexisting English content",after)
                self.assertIn("Existing description",after)
                self.assertEqual(after.count(m.MARKER),1)
                self.assertEqual(after.count("<figure>"),len(m.ROUTES[page][1]))
                self.assertEqual(after.count("owner_gallery_20261015_b"),2*len(m.ROUTES[page][1]))
                self.assertEqual(after.count("{% endblock %}"),3)
                with self.assertRaises(ValueError):
                    m.patch(page,after)
    def test_gallery_shows_all_10_original_composites_individually(self):
        after=m.patch("gallery",self.template())
        for number in range(1,11):
            self.assertEqual(after.count("photo-"+f"{number:02d}"+".png"),2)
        self.assertEqual(after.count("<figure>"),10)
    def test_content_block_remains_valid_and_scope_is_fixed(self):
        with self.assertRaises(ValueError):
            m.patch("unrelated",self.template())
        with self.assertRaises(ValueError):
            m.patch("about","<h1>Empty unrelated file</h1>")
        self.assertEqual(set(m.ROUTES),{"home","about","projects","posts","gallery","resume","activities","memories","stories"})
        self.assertEqual(len(m.SHA),10)
        self.assertEqual(len(set(m.SHA)),10)
        self.assertEqual(len(m.SIZES),10)
    def test_existing_templates_without_static_tag_are_supported(self):
        before=self.template().replace("{% load static %}","")
        out=m.patch("about",before)
        self.assertEqual(out.count("{% load static %}"),1)
        self.assertIn("Preexisting English content",out)
    def test_archive_only_if_present(self):
        archive=pathlib.Path(__file__).resolve().parents[1]/"assets/mojtaba_new_10_original_photos.zip"
        if archive.exists():
            m.verify_archive(archive)

if __name__=="__main__":unittest.main()
