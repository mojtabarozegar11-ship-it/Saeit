"""Unit tests for fail-closed additive personal V18 upgrades."""
import importlib.util
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "scripts/mojtaba_personal_v18_enterprise_refresh.py"
spec=importlib.util.spec_from_file_location("personal_v18",SOURCE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def base():
    return """{% load static %}
<html><head>
<meta name="theme-color" content="#101c2b">
<meta name="color-scheme" content="light">
<meta name="description" content="{% block description %}The personal website of Mojtaba Roozegar: work, journeys, memories, fiction and thoughtful writing.{% endblock %}">
<title>{% block title %}Mojtaba Roozegar — Personal Website{% endblock %}</title>
<meta property="og:title" content="{% block og_title %}Mojtaba Roozegar — Personal Website{% endblock %}">
<meta property="og:description" content="{% block og_description %}An independent personal collection of work, ideas, memories and original stories.{% endblock %}">
</head><body>Original branding<nav>Original links</nav></body></html>"""

def page(name):
    markers="\n".join('<section id="'+mark+'">KEEP</section>' for mark in mod.PRESERVE)
    if name=="home": markers+='<img id="mpw-primary-personal-profile-20261016" src="official.webp">'
    return "{% extends 'personal_site/base.html' %}\n{% block content %}<h1>Original "+name+"</h1>\n"+markers+"\n{% endblock %}"

class UpgradeTests(unittest.TestCase):
    def test_base_preserves_nav_and_adds_only_dark_seo(self):
        start=base();out=mod.patch("base",start)
        self.assertIn('content="#101111"',out)
        self.assertIn('content="dark"',out)
        self.assertIn("Enterprise Website Collaboration Enquiries",out)
        self.assertIn("original-not-present",out+"original-not-present")
        self.assertIn("Original branding<nav>Original links</nav>",out)
        self.assertEqual(out.count(mod.MARK),1)
        with self.assertRaises(ValueError):mod.patch("base",out)

    def test_five_pages_are_additive(self):
        for name in ("home","posts","resume","projects","contact"):
            before=page(name)
            after=mod.patch(name,before)
            self.assertIn("<h1>Original "+name+"</h1>",after)
            self.assertTrue(all(before.count(m)<=after.count(m) for m in mod.PRESERVE))
            self.assertEqual(after.count('<section id="'+mod.MARK+"-"+name+'"'),1)
            self.assertIn('/mojtaba.roozegar/contact/',after)
            self.assertIn("{% endblock %}",after)

    def test_refuse_missing_93_article_sections(self):
        with self.assertRaises(ValueError):mod.patch("posts","{% block content %}Empty{% endblock %}")
        with self.assertRaises(ValueError):mod.patch("home",page("home").replace("mpw-primary-personal-profile-20261016","different"))

    def test_no_change_to_original_navigational_links(self):
        before=page("resume").replace('<h1>Original resume</h1>','<h1>Original resume</h1><a href="/mojtaba.roozegar/about/">About</a>')
        after=mod.patch("resume",before)
        self.assertIn('<a href="/mojtaba.roozegar/about/">About</a>',after)
        self.assertEqual(before.count("{% endblock %}"),after.count("{% endblock %}"))

    def test_dynamic_detail_seo(self):
        self.assertIn("{{ item.title }}",mod.seo_fallback("title"))
        self.assertIn("post_detail",mod.seo_fallback("description"))
        self.assertNotIn("<script",mod.seo_fallback("description"))

    def test_protected_scope_exactly_six(self):
        self.assertEqual(len(mod.PAGES),6)
        self.assertEqual(mod.PAGES["base"],"templates/personal_site/base.html")
        self.assertNotIn("zomorod",str(mod.PAGES).lower())
        self.assertNotIn("public_html",str(mod.PAGES).lower())
if __name__=="__main__":unittest.main()
