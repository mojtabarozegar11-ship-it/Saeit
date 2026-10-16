"""Approved owner logo swap: preserving original and site content."""
from pathlib import Path
import struct
import unittest

ROOT=Path(__file__).resolve().parents[1]
LOGO=ROOT/"content/zomorod-brand/logo-transparent-128.png"
ORIGINAL=ROOT/"core/static/site/company/company-logo.png"
PAGES=[
    "content/zomorod-new-home/index.html",
    "content/zomorod-nova-pages/company.html",
    "content/zomorod-nova-pages/about.html",
    "content/zomorod-nova-pages/services.html",
    "content/zomorod-nova-pages/industry.html",
    "content/zomorod-nova-pages/research.html",
    "content/zomorod-nova-pages/knowledge.html",
    "templates/admin/base_site.html",
]

class TestZomorodTransparentBrand(unittest.TestCase):
    def test_genuine_transparent_png_with_alpha(self):
        data=LOGO.read_bytes()
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(data[12:16],b"IHDR")
        self.assertEqual(struct.unpack(">II",data[16:24]),(128,128))
        self.assertIn(b"tRNS",data,"Palette transparency chunk required")
        self.assertGreater(len(data),4000)
        self.assertTrue(ORIGINAL.is_file(),"Original logo must remain intact")

    def test_all_main_host_templates_refer_to_new_logo_without_other_changes(self):
        marker="/static/site/company/company-logo-transparent.png"
        old="/static/site/company/company-logo.png"
        for name in PAGES:
            with self.subTest(path=name):
                doc=(ROOT/name).read_text(encoding="utf-8")
                self.assertIn(marker,doc)
                self.assertNotIn(old,doc)
        self.assertIn("zm-nova-home-2026-v1",(ROOT/PAGES[0]).read_text())
        self.assertIn('{% extends "admin/base.html" %}',(ROOT/PAGES[-1]).read_text())

if __name__=="__main__":
    unittest.main()
