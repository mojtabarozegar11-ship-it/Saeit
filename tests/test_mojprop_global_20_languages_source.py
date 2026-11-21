"""Verify MOJ PROP's global SEO source without accessing production or payments."""
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("mojprop_20",ROOT/"scripts"/"mojprop_multilang_20261121_build.py")
mod=importlib.util.module_from_spec(sp)
sp.loader.exec_module(mod)

class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.html_lang=None
        self.links=[]
        self.alts=[]
        self.canon=[]
        self.robots=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="html":self.html_lang=a.get("lang")
        if tag=="a":self.links.append(a.get("href"))
        if tag=="link" and a.get("rel")=="alternate":self.alts.append(a)
        if tag=="link" and a.get("rel")=="canonical":self.canon.append(a.get("href"))
        if tag=="meta" and a.get("name")=="robots":self.robots.append(a.get("content"))

class GlobalPropSEOTests(unittest.TestCase):
    def test_exactly_20_languages_and_distinct_paths(self):
        self.assertEqual(len(mod.L),19)
        self.assertEqual(len(mod.NAMES),20)
        self.assertEqual(set(mod.NAMES)-{"en"}, {r[0] for r in mod.L})
        paths=[mod.path(c) for c in mod.NAMES]
        self.assertEqual(len(set(paths)),20)
        self.assertEqual(mod.path("en"),"/moj-prop/")
    def test_google_hreflang_codes_and_reciprocity(self):
        self.assertEqual(len(mod.VALID),19)
        self.assertNotIn("pcm",mod.VALID)
        self.assertIn("ar-EG",mod.VALID)
        self.assertEqual(len(set(mod.VALID)),19)
        for item in mod.L:
            code=item[0]
            parsed=Tags()
            source=mod.localized(item)
            parsed.feed(source)
            self.assertEqual(parsed.html_lang,code)
            self.assertEqual(parsed.canon,["https://mojplaywin.com"+mod.path(code)])
            self.assertIn("index,follow,max-image-preview:large",parsed.robots)
            self.assertIn("/moj-prop/",parsed.links)
            self.assertIn(mod.path(code),parsed.links)
            expected=set(mod.VALID)|{"x-default"}
            if code=="pcm":
                self.assertEqual(parsed.alts,[])
            else:
                self.assertEqual({a["hreflang"] for a in parsed.alts},expected)
                self.assertEqual(len(parsed.alts),20)
                self.assertEqual({a["hreflang"]:a["href"] for a in parsed.alts}["en"],"https://mojplaywin.com/moj-prop/")
            self.assertIn(item[2],source)
    def test_directory_exposes_all_languages(self):
        source=mod.directory_page()
        for code in mod.NAMES:
            self.assertIn('href="'+mod.path(code)+'"',source)
        self.assertEqual(source.count('name="robots" content="index,follow"'),1)
    def test_non_native_hreflang_rejected_and_international_terms_not_promised(self):
        self.assertNotIn('hreflang="pcm"',mod.hreflangs())
        self.assertIn('hreflang="x-default"',mod.hreflangs())
        for item in mod.L:
            source=mod.localized(item)
            self.assertNotIn('data-pay-now',source)
            self.assertNotIn('type="submit"',source)
            self.assertNotIn('guaranteed profit',source.lower())

if __name__=="__main__":
    unittest.main()
