"""Offline regression tests; no live server or external Google accounts used."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
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
        self.assertEqual(report["embedded_data_image_tags"], 1)
        self.assertEqual(report["pages_with_embedded_data_images"], [P])
        self.assertEqual(report["pages_without_public_html_img_urls"], [])
        self.assertEqual({entry["reason"] for entry in report["excluded_images"]},
                         {"embedded_data_uri", "outside_public_origin"})
        self.assertNotIn("abc", str(report["excluded_images"]))

    def test_store_product_page_without_html_img_is_reported(self):
        product = module.ORIGIN + "/store/product/225/"
        html = b'<html><head><link rel="canonical" href="https://mojplaywin.com/store/product/225/"></head><body><h1>Taniya Baker</h1></body></html>'
        def loader(url, method):
            return 200, "text/html", html, product, ""
        report, entries = module.audit(sitemap(product), loader)
        self.assertEqual(report["pages_without_html_img_tags"], [product])
        self.assertEqual(report["pages_without_public_html_img_urls"], [product])
        self.assertEqual(report["html_img_tags"], 0)
        self.assertEqual(report["pages_without_images"], [product])
        self.assertFalse(entries)

    def test_embedded_only_taniya_studio_page_is_identified(self):
        studio = module.ORIGIN + "/taniya/"
        html = b'<html><head><meta property="og:image" content="/static/taniya-cover.webp"></head><body><img src="data:image/jpeg;base64,REDACTED" alt="Taniya cover"></body></html>'
        def loader(url, method):
            return 200, "text/html", html, studio, ""
        report, entries = module.audit(sitemap(studio), loader)
        self.assertEqual(report["html_img_tags"], 1)
        self.assertEqual(report["embedded_data_image_tags"], 1)
        self.assertEqual(report["pages_without_html_img_tags"], [])
        self.assertEqual(report["pages_without_public_html_img_urls"], [studio])
        self.assertEqual(report["pages_with_embedded_data_images"], [studio])
        self.assertEqual(report["pages_with_metadata_only_images"], [studio])
        self.assertEqual(entries[studio], [module.ORIGIN + "/static/taniya-cover.webp"])
        self.assertNotIn("REDACTED", str(report))

    def test_deferred_image_without_src_is_audited_but_not_sitemapped(self):
        html = b'<img data-src="/static/game-cover.webp" alt="Game cover">'
        def loader(url, method):
            return 200, "text/html", html, P, ""
        report, entries = module.audit(sitemap(P), loader)
        self.assertEqual(report["deferred_image_tags"], 1)
        self.assertEqual(report["pages_with_deferred_images"], [P])
        self.assertEqual(report["pages_without_public_html_img_urls"], [P])
        self.assertFalse(entries)

    def test_signed_reference_not_logged(self):
        html = b'<img src="/static/secret.webp?token=never-log-me" alt="">'
        def loader(url, method):
            return 200, "text/html", html, P, ""
        report, _ = module.audit(sitemap(P), loader)
        self.assertEqual(report["excluded_images"],
                         [{"page": P, "reason": "protected_or_signed_reference"}])
        self.assertNotIn("never-log-me", str(report))

    def test_parallel_verification_emits_only_reachable_public_images(self):
        q = module.ORIGIN + "/research/"
        broken = module.ORIGIN + "/static/absent.webp"
        html = b'<img src="/static/game-cover.webp" alt="Game"><img src="/static/absent.webp" alt="Broken">'
        def loader(url, method):
            if method == "GET":
                return 200, "text/html", html, url, ""
            if url == I:
                return 200, "image/webp", b"", url, ""
            raise HTTPError(url, 404, "Not Found", {}, None)

        report, entries, inventory = module.audit_parallel(sitemap(P, q), loader,
                                                            workers=2, verify_images=True)
        self.assertEqual(set(entries), {P, q})
        self.assertEqual(entries[P], [I])
        self.assertEqual(inventory[P], [I, broken])
        self.assertEqual(report["verified_image_urls"], 1)
        self.assertEqual(report["unique_public_images"], 2)
        self.assertEqual(report["image_sitemap_image_entries"], 2)
        self.assertEqual(report["unverified_images"], [{"url": broken, "reason": "HTTP_404"}])
        self.assertEqual(report["pages_without_verified_images"], [])

    def test_parallel_verification_get_fallback_for_head_405(self):
        calls = []
        def loader(url, method):
            calls.append((url, method))
            if url == P:
                return 200, "text/html", b'<img src="/static/game-cover.webp">', P, ""
            if method == "HEAD":
                raise HTTPError(url, 405, "Method Not Allowed", {}, None)
            return 200, "image/webp", b"image bytes", url, ""
        report, entries, inventory = module.audit_parallel(sitemap(P), loader,
                                                            workers=2, verify_images=True)
        self.assertEqual(entries[P], [I])
        self.assertEqual(inventory[P], [I])
        self.assertIn((I, "HEAD"), calls)
        self.assertIn((I, "GET"), calls)
        self.assertEqual(report["image_validation_mode"], "verified_HEAD_with_GET_on_405_501")

    def test_parallel_inventory_with_no_image_page(self):
        def loader(url, method):
            return 200, "text/html", b'<h1>Text-only product</h1>', P, ""
        report, entries, inventory = module.audit_parallel(sitemap(P), loader,
                                                            workers=2, verify_images=False)
        self.assertEqual(entries, {})
        self.assertEqual(inventory, {})
        self.assertEqual(report["pages_without_public_html_img_urls"], [P])

    def test_parallel_worker_limit(self):
        with self.assertRaises(ValueError):
            module.audit_parallel(sitemap(P), workers=5)

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
