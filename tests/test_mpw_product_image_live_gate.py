"""Offline production release-gate checks; no live network or writes."""

import importlib.util
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "mpw_product_image_live_gate", SCRIPTS / "mpw_product_image_live_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

ATELIER = gate.ORIGIN + "/static/site/mojplaywin-products/atelier-original.webp"


def html(path, srcs=(), canonical=True):
    url = gate.ORIGIN + path
    head = f'<link rel="canonical" href="{url}">' if canonical else ""
    imgs = "".join(f'<img src="{src}" alt="Original commercial illustration">'
                   for src in srcs)
    return f"<html><head>{head}</head><body>{imgs}</body></html>".encode()


def loader_for(commercial_images=True, *, embedded=False, head_405=False):
    covers = {**gate.COVERS, 879: ATELIER}
    pages = {}
    for path in gate.LANDINGS:
        if not commercial_images:
            pages[path] = html(path)
        elif path == "/store/":
            pages[path] = html(path, covers.values())
        elif path == "/taniya/":
            pages[path] = html(path, [gate.COVERS[225]])
        else:
            product_id = int(path.strip("/").split("/")[-1])
            pages[path] = html(path, [covers[product_id]])
    if embedded:
        pages["/taniya/"] = html("/taniya/") + b'<img src="data:image/jpeg;base64,SECRET">'

    def loader(url, method):
        if url.startswith(gate.ORIGIN + "/static/"):
            if method == "HEAD" and head_405:
                raise HTTPError(url, 405, "Method Not Allowed", {}, None)
            return 200, "image/webp", b"" if method == "HEAD" else b"WEBP", url, ""
        path = url.removeprefix(gate.ORIGIN)
        return 200, "text/html", pages[path], url, ""

    return loader


class TestCommercialImageGate(unittest.TestCase):
    def test_current_text_only_product_pages_cannot_pass(self):
        report = gate.inspect(loader_for(commercial_images=False))
        self.assertEqual(report["release_gate"], "HOLD")
        self.assertEqual(report["pages_with_issues"], 5)
        self.assertEqual(report["verified_cover_urls"], 2)
        self.assertIn("no_public_direct_img_src", report["pages"][1]["issues"])
        self.assertIn("product_cover_url_unknown", report["pages"][3]["issues"])

    def test_all_three_real_cover_mappings_and_html_images_pass(self):
        report = gate.inspect(loader_for(), atelier_cover=ATELIER)
        self.assertEqual(report["release_gate"], "PASS")
        self.assertEqual(report["pages_with_issues"], 0)
        self.assertEqual(report["verified_cover_urls"], 3)

    def test_unknown_atelier_cover_keeps_release_on_hold(self):
        report = gate.inspect(loader_for())
        self.assertEqual(report["release_gate"], "HOLD")
        self.assertIn("product_cover_url_unknown", report["pages"][3]["issues"])

    def test_rejects_private_and_cross_host_supplied_assets(self):
        for url in ("https://evil.example/cover.webp",
                    gate.ORIGIN + "/private/cover.webp",
                    gate.ORIGIN + "/static/cover.webp?token=secret"):
            with self.assertRaises(ValueError):
                gate.inspect(loader_for(), atelier_cover=url)

    def test_data_uri_is_reported_without_payload(self):
        report = gate.inspect(loader_for(embedded=True), atelier_cover=ATELIER)
        self.assertEqual(report["release_gate"], "HOLD")
        self.assertIn("embedded_image_data_uri", report["pages"][-1]["issues"])
        self.assertIn("invalid_embedded_image_data_uri", report["pages"][-1]["issues"])
        self.assertEqual(report["pages"][-1]["invalid_embedded_data_img_count"], 1)
        self.assertNotIn("SECRET", str(report))

    def test_head_405_get_fallback_for_cover_asset(self):
        report = gate.inspect(loader_for(head_405=True), atelier_cover=ATELIER)
        self.assertEqual(report["release_gate"], "PASS")

    def test_static_fallback_marker_is_reported_even_when_django_template_has_images(self):
        delegate = loader_for(commercial_images=False)
        def loader(url, method):
            status, mime, data, final, robots = delegate(url, method)
            if url == gate.ORIGIN + "/store/" and method == "GET":
                data += b"<!-- MPW_STATIC_STORE_FALLBACK_V1 -->"
            return status, mime, data, final, robots
        report = gate.inspect(loader)
        self.assertEqual(report["release_gate"], "HOLD")
        self.assertEqual(report["store_live_renderer_marker"],
                         "MPW_STATIC_STORE_FALLBACK_V1")
        self.assertEqual(report["pages"][0]["html_img_count"], 0)


if __name__ == "__main__":
    unittest.main()

