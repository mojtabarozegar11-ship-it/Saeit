from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest
import zipfile

scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location(
    "sku879_multiview", scripts / "mpw_sku879_private_candidate_12view_qa_20261026.py"
)
wide = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wide)
from mpw_sku879_private_browser_qa_20261026 import safe_extract, browser_views


class BrowserMatrixTests(unittest.TestCase):
    def test_exact_twelve_breakpoints(self):
        self.assertEqual(len(wide.VIEWPORTS), 12)
        self.assertEqual(wide.VIEWPORTS[0], (320, 720))
        self.assertEqual(wide.VIEWPORTS[-1], (1920, 1080))

    def test_pure_gate_detects_missing_alt_and_bad_form_control(self):
        rows = []
        for width, height in wide.VIEWPORTS:
            rows.append({
                "requested_viewport": [width, height],
                "device_screen_width": width,
                "visual_viewport_width": width,
                "viewport_width": width,
                "viewport_height": height,
                "ready": True,
                "title_present": True,
                "body_char_count": 200,
                "broken_images": 0,
                "horizontal_overflow_px": 0,
                "screenshot_valid": True,
                "images_missing_alt": 0,
                "unlabeled_buttons": 0,
                "unlabeled_form_controls": 0,
                "unsafe_blank_links": 0,
                "broken_same_page_anchors": 0,
            })
        checks = wide.evaluate_rows(rows)
        self.assertTrue(all(checks.values()))
        rows[3]["images_missing_alt"] = 1
        rows[5]["unlabeled_form_controls"] = 1
        checks = wide.evaluate_rows(rows)
        self.assertFalse(checks["image_alt_attributes_present"])
        self.assertFalse(checks["form_control_labels_present"])
        self.assertTrue(checks["no_visual_overflow"])

    def test_actual_browser_three_responsive_sizes_and_accessibility_shapes(self):
        html = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Interior Design</title>"
            "<style>*{box-sizing:border-box}body{margin:0}main{margin:auto;max-width:900px;"
            "padding:16px}input{max-width:100%;width:100%}</style>"
            "</head><body><main><h1>Interior Design</h1>"
            "<p>Professional residential interior design portfolio.</p>"
            "<form><label for='email'>Email</label><input id='email' type='email'>"
            "<button type='button'>Contact Us</button></form>"
            "<a href='#about'>Learn more</a><h2 id='about'>About us</h2>"
            "</main></body></html>"
        )
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "synthetic.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("index.html", html)
            root = Path(temp) / "root"
            root.mkdir()
            entry = safe_extract(archive, root)
            views = browser_views(root, entry, ((320, 720), (390, 844), (1440, 900)))
            self.assertEqual(len(views), 3)
            for row in views:
                self.assertTrue(row["screenshot_valid"])
                self.assertEqual(row["horizontal_overflow_px"], 0)
                self.assertEqual(row["unlabeled_form_controls"], 0)
                self.assertEqual(row["unlabeled_buttons"], 0)
                self.assertEqual(row["broken_same_page_anchors"], 0)


if __name__ == "__main__":
    unittest.main()
