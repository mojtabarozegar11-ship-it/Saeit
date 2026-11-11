"""Offline regression tests; no live server or external Google accounts used."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mpw_google_images_audit.py"
spec = importlib.util.spec_from_file_location("mpw_google_images_audit", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sitemap(*urls):
    ns = module.NS_SITEMAP
    r = ET.Element("{" + ns + "}urlset")
    for url in urls:
        e = ET.SubElement(r, "{" + ns + "}url")
        ET.SubElement(e, "{" + ns + "}loc").text = url
    return ET.tostring(r)


P = module.ORIGIN + "/games/"
I = module.ORIGIN + "/static/game-cover.webp"


class TestImageAudit(unittest.TestCase):
    def test_untrusted_host_rejected(self):
        self.assertFalse(module.public_url("https://evil.example/static/x.webp", image=True))
        self.assertFalse(module.public_url("http://mojplaywin.com/static/x.webp", image=True))

    def test_private_files_and_checkout_rejected(self):
        for path in ("/private/a.webp", "/store/product/72/checkout/", "/downloads/a.webp", "/x.pdf"):
            self.assertFalse(module.public_url(module.ORIGIN + path))

    def test_non_image_asset_excluded(self):
        self.assertIsNone(module.normalized_url("/static/site.css", P, image=True))

    def test_signed_query_excluded_from_public_sitemap(self):
        self.assertFalse(module.public_url(module.ORIGIN + "/static/a.webp?token=private", image=True))

    def test_duplicate_and_foreign_sitemap_entries(self):
        urls = module.sitemap_pages(sitemap(P, P, "https://other.example/", module.ORIGIN + "/admin/"))
        self.assertEqual(urls, [P])

    def test_sitemap_index_not_accepted(self):
        with self.assertRaises(ValueError):
            module.sitemap_pages(b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>')

    def test_meta_robots_noimageindex(self):
        self.assertTrue(module.blocked_by_robots("max-image-preview:large, noimageindex"))

    def test_image_and_og_discovery(self):
        html = b'''<html><head><link rel="canonical" href="https://mojplaywin.com/games/">
          <meta property="og:image" content="/static/game-cover.webp"></head>
          <body><img src="/static/game-cover.webp" alt="Game cover"><img src="/static/x.webp" alt="">
          <img src="/static/missing.webp"></body></html>'''
        def loader(url, method):
            return (200, "text/html", html, P, "")
        report, entries = module.audit(sitemap(P), loader=loader)
        self.assertEqual(entries[P], [I, module.ORIGIN+"/static/x.webp", module.ORIGIN+"/static/missing.webp"])
        self.assertEqual(report["empty_alt_occurrences"], 1)
        self.assertEqual(report["missing_alt_occurrences"], 1)
        self.assertEqual(report["unique_public_images"], 3)

    def test_noncanonical_page_skipped(self):
        def loader(url, method):
            return (200, "text/html", b'<html><head><link rel="canonical" href="https://mojplaywin.com/about/"></head><body><img src="/static/x.webp"></body></html>', P, "")
        report, entries = module.audit(sitemap(P), loader)
        self.assertEqual(report["indexable_pages"], 0)
        self.assertFalse(entries)

    def test_verified_images_only(self):
        html = b'<img src="/static/game-cover.webp" alt="Cover"><img src="/static/broken.webp" alt="Broken">'
        def loader(url, method):
            if method == "GET":
                return 200, "text/html", html, P, ""
            if url == I:
                return 200, "image/webp", b"", url, ""
            return 404, "text/plain", b"", url, ""
        report, entries = module.audit(sitemap(P), loader, verify_images=True)
        self.assertEqual(entries[P], [I])
        self.assertEqual(report["verified_image_urls"], 1)
        self.assertEqual(report["unique_public_images"], 2)

    def test_xrobots_blocks_image(self):
        def loader(url, method):
            if method == "GET":
                return 200, "text/html", b'<img src="/static/game-cover.webp">', P, ""
            return 200, "image/webp", b"", url, "noimageindex"
        report, entries = module.audit(sitemap(P), loader, verify_images=True)
        self.assertFalse(entries)
        self.assertEqual(report["verified_image_urls"], 0)

    def test_noimageindex_blocks_entire_page(self):
        def loader(url, method):
            return 200, "text/html", b'<html><head><meta name="robots" content="noimageindex"></head><body><img src="/static/game-cover.webp"></body></html>', P, ""
        report, entries = module.audit(sitemap(P), loader)
        self.assertEqual(report["indexable_pages"], 0)
        self.assertEqual(entries, {})

    def test_page_xrobots_header_blocks(self):
        def loader(url, method):
            return 200, "text/html", b'<img src="/static/game-cover.webp">', P, "noindex"
        report, entries = module.audit(sitemap(P), loader)
        self.assertEqual(report["indexable_pages"], 0)
        self.assertEqual(entries, {})

    def test_external_and_data_image_filtered(self):
        html = b'<img src="data:image/svg+xml,abc" alt=""><img src="https://example.org/a.jpg"><img src="/static/game-cover.webp">'
        def loader(url, method):
            return 200, "text/html", html, P, ""
        report, entries = module.audit(sitemap(P), loader)
        self.assertEqual(entries[P], [I])
        self.assertEqual(len(report["excluded_images"]), 2)

    def test_xml_uses_google_image_namespace(self):
        data = module.xml_image_sitemap({P: [I]})
        xml = ET.fromstring(data)
        rows = xml.findall("{" + module.NS_SITEMAP + "}url")
        self.assertEqual(len(rows), 1)
        image_loc = rows[0].findtext("{" + module.NS_IMAGE + "}image/{" + module.NS_IMAGE + "}loc")
        self.assertEqual(image_loc, I)

    def test_no_existing_output_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "sitemap.xml"
            path.write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                module.new_file_only(str(path), b"replacement")
            self.assertEqual(path.read_text(encoding="utf-8"), "existing")


if __name__ == "__main__":
    unittest.main()
