import base64
from pathlib import Path
import importlib.util
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location(
    "sku879_browser",
    Path(__file__).resolve().parents[1] / "scripts/mpw_sku879_private_browser_qa_20261026.py",
)
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)

PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+nmv8AAAAASUVORK5CYII="
)


class PrivateBrowserQaTests(unittest.TestCase):
    def make_archive(self, path, missing=False, wide=False):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("index.html",
                "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>Client-Ready Kit</title>"
                "<style>html,body{margin:0}main{max-width:960px;margin:auto;padding:16px}"
                "img{max-width:100%;height:auto}" +
                ("main{min-width:453px}" if wide else "") +
                "</style></head><body><main>"
                "<h1>Functional Website Kit</h1><p>This is a real local browser "
                "rendering smoke test across desktop and mobile viewports.</p>"
                "<img alt='Hero' src='" + ("missing.png" if missing else "hero.png") + "'>"
                "</main></body></html>")
            if not missing:
                archive.writestr("hero.png", PIXEL)

    def test_valid_private_kit_renders_real_desktop_and_mobile_viewports(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "site.zip"
            self.make_archive(archive)
            extraction = Path(temp) / "extracted"
            extraction.mkdir(mode=0o700)
            entry = qa.safe_extract(archive, extraction)
            self.assertEqual(entry, "index.html")
            views = qa.browser_views(extraction, entry)
            self.assertEqual(len(views), 2)
            self.assertEqual([v["requested_viewport"][0] for v in views], [390, 1440])
            self.assertEqual(views[0]["device_screen_width"], 390)
            self.assertEqual(views[0]["visual_viewport_width"], 390)
            self.assertEqual(views[1]["viewport_width"], 1440)
            self.assertEqual([v["viewport_height"] for v in views], [844, 900])
            for view in views:
                self.assertTrue(view["ready"])
                self.assertTrue(view["title_present"])
                self.assertGreater(view["body_char_count"], 30)
                self.assertEqual(view["broken_images"], 0)
                self.assertLessEqual(view["horizontal_overflow_px"], 2)
                self.assertTrue(view["screenshot_valid"])

    def test_broken_local_image_is_detected_by_actual_browser(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "missing.zip"
            self.make_archive(archive, missing=True)
            extraction = Path(temp) / "extracted"
            extraction.mkdir(mode=0o700)
            entry = qa.safe_extract(archive, extraction)
            views = qa.browser_views(extraction, entry)
            self.assertEqual(len(views), 2)
            self.assertTrue(all(v["broken_images"] >= 1 for v in views))

    def test_mobile_min_width_reports_real_physical_overflow(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "too-wide.zip"
            self.make_archive(archive, wide=True)
            extraction = Path(temp) / "extracted"
            extraction.mkdir(mode=0o700)
            entry = qa.safe_extract(archive, extraction)
            views = qa.browser_views(extraction, entry)
            self.assertEqual(views[0]["device_screen_width"], 390)
            self.assertEqual(views[0]["visual_viewport_width"], 390)
            self.assertGreaterEqual(views[0]["horizontal_overflow_px"], 60)
            self.assertTrue(any(item["min_width"] == "453px"
                                for item in views[0]["overflowing_shapes"]))

    def test_session_creation_has_bounded_startup_budget_without_retry(self):
        from unittest.mock import patch

        with patch.object(qa.urllib.request, "urlopen") as urlopen, patch.object(
            qa.json, "load", return_value={"value": {"sessionId": "test-session"}}
        ):
            result = qa.webdriver_request(9999, "POST", "/session", {"capabilities": {}})
            self.assertEqual(result["sessionId"], "test-session")
            self.assertEqual(urlopen.call_args.kwargs["timeout"], 60)
            qa.webdriver_request(9999, "GET", "/status")
            self.assertEqual(urlopen.call_args.kwargs["timeout"], 28)
            self.assertEqual(urlopen.call_count, 2)

    def test_zip_path_traversal_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "escape.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("../outside.html", "<title>unsafe</title>")
                package.writestr("index.html", "<title>safe</title>")
            root = Path(temp) / "safe"
            root.mkdir()
            with self.assertRaisesRegex(RuntimeError, "ZIP_UNSAFE_MEMBER"):
                qa.safe_extract(archive, root)
            self.assertFalse((Path(temp) / "outside.html").exists())

    def test_missing_index_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "missing-index.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("page.html", "<title>No index</title>")
            with self.assertRaisesRegex(RuntimeError, "WEBSITE_INDEX_MISSING"):
                qa.safe_extract(archive, Path(temp) / "extract")


if __name__ == "__main__":
    unittest.main()
