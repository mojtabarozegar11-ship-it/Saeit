import base64
from pathlib import Path
import importlib.util
import tempfile
import unittest
import zipfile

base = Path(__file__).resolve().parents[1] / "scripts"
import sys
sys.path.insert(0, str(base))
spec = importlib.util.spec_from_file_location(
    "private_mobile_repair", base / "mpw_sku879_private_mobile_repair_20261026.py"
)
mobile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mobile)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+nmv8AAAAASUVORK5CYII="
)


class MobileRepairTests(unittest.TestCase):
    def fixture(self, archive):
        long_word = "responsive" * 70
        html = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Interior Website Kit</title><style>"
            "body{margin:0}main{display:flex;max-width:960px;margin:auto;padding:12px}"
            "main div{min-width:auto}img{max-width:100%;height:auto}"
            "@media(min-width:768px){main p{overflow-wrap:anywhere}}"
            "</style></head><body><main><div><h1>Interior Design Portfolio</h1>"
            "<p>" + long_word + "</p><img src='hero.png' alt='Hero'></div>"
            "</main></body></html>"
        )
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("index.html", html)
            package.writestr("hero.png", PNG)
            package.writestr("assets/readme.txt", "Untouched product asset")
        return html

    def test_injection_requires_unique_head(self):
        with self.assertRaisesRegex(RuntimeError, "CANDIDATE_HTML_HEAD_INVALID"):
            mobile.inject("<html><body>Missing head</body></html>", mobile.BASE_STYLE)
        with self.assertRaisesRegex(RuntimeError, "CANDIDATE_HTML_HEAD_INVALID"):
            mobile.inject("<head></head><head></head>", mobile.BASE_STYLE)

    def test_original_non_html_assets_remain_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.zip"
            out = Path(temp) / "candidate.zip"
            html = self.fixture(source)
            changed = mobile.inject(html, mobile.BASE_STYLE).encode("utf-8")
            result_hash = mobile.repackage(source, out, "index.html", changed)
            self.assertEqual(mobile.sha256_file(out), result_hash)
            with zipfile.ZipFile(source) as s, zipfile.ZipFile(out) as c:
                self.assertEqual(s.namelist(), c.namelist())
                self.assertEqual(s.read("hero.png"), c.read("hero.png"))
                self.assertEqual(s.read("assets/readme.txt"), c.read("assets/readme.txt"))
                self.assertIn(mobile.MARKER.encode(), c.read("index.html"))
                self.assertNotIn(mobile.MARKER.encode(), s.read("index.html"))

    def test_real_browser_can_repair_intrinsic_text_overflow(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.zip"
            self.fixture(source)
            extracted = Path(temp) / "unpacked"
            extracted.mkdir()
            entry = mobile.safe_extract(source, extracted)
            baseline = mobile.browser_views(extracted, entry)
            self.assertGreater(baseline[0]["horizontal_overflow_px"], 2)
            src = (extracted / entry).read_text(encoding="utf-8")
            (extracted / entry).write_text(
                mobile.inject(src, mobile.BASE_STYLE), encoding="utf-8"
            )
            repaired = mobile.browser_views(extracted, entry)
            self.assertTrue(mobile.passes(repaired), [
                {k: v[k] for k in (
                    "requested_viewport", "viewport_width", "viewport_height",
                    "device_screen_width", "visual_viewport_width",
                    "horizontal_overflow_px", "broken_images", "screenshot_valid",
                    "body_char_count", "ready", "title_present"
                )} for v in repaired])
            self.assertTrue(all(row["broken_images"] == 0 for row in repaired))


if __name__ == "__main__":
    unittest.main()
