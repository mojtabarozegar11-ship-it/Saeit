"""Quality and publication blocking tests for the CPU Image Studio."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    from PIL import Image
except ModuleNotFoundError as exc:
    if exc.name != "PIL":
        raise
    Image = None

if Image is not None:
    from image_quality_report import report
else:
    report = None


@unittest.skipIf(Image is None, "Pillow is tested in dedicated image QA CI only")
class TestImageQualityGate(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.image = Path(self.directory.name) / "valid.png"
        # Deterministic, complex image to exercise diagnostic quality metrics.
        png = Image.new("RGB", (512, 512))
        pixels = png.load()
        for y in range(512):
            for x in range(512):
                pixels[x, y] = ((x * 13 + y * 7) % 256,
                                (x * 5 + y * 19) % 256,
                                (x * 3 + y * 29) % 256)
        png.save(self.image, "PNG")

    def test_real_png_is_verified_but_not_commercial(self):
        r = report(self.image, engine="github-runner-cpu",
                   preset="orchard", steps=8, run_id="test")
        self.assertTrue(r["technical_png_valid"])
        self.assertFalse(r["commercial_ready"])
        self.assertFalse(r["publish_allowed"])
        self.assertFalse(r["auto_store_upload_allowed"])
        self.assertTrue(r["manual_review_required"])
        self.assertEqual(r["sha256"], hashlib.sha256(self.image.read_bytes()).hexdigest())
        self.assertEqual(r["dimensions"], {"width": 512, "height": 512})
        self.assertIn("resolution_below_commercial_minimum", r["block_reasons"])
        self.assertGreater(r["diagnostic_metrics"]["luma_entropy_bits"], 1)

    def test_increased_resolution_still_requires_human_approval(self):
        Image.new("RGB", (1024, 1024), (110, 100, 150)).save(self.image)
        r = report(self.image, engine="vps-comfyui-sse2",
                   preset="product", steps=20)
        self.assertFalse(r["publish_allowed"])
        self.assertTrue(r["manual_review_required"])
        self.assertNotIn("resolution_below_commercial_minimum", r["block_reasons"])

    def test_corrupted_image_rejected(self):
        self.image.write_bytes(b"not a png" * 400)
        with self.assertRaisesRegex(ValueError, "PNG_SIGNATURE_INVALID"):
            report(self.image, engine="github-runner-cpu", preset="orchard", steps=8)

    def test_invalid_parameters_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_ENGINE"):
            report(self.image, engine="shell", preset="orchard", steps=8)
        with self.assertRaisesRegex(ValueError, "INVALID_PRESET"):
            report(self.image, engine="github-runner-cpu", preset="unknown", steps=8)
        with self.assertRaisesRegex(ValueError, "INVALID_STEPS"):
            report(self.image, engine="github-runner-cpu", preset="orchard", steps=999)

    def test_symlink_rejected(self):
        symlink = Path(self.directory.name) / "symlink.png"
        symlink.symlink_to(self.image)
        with self.assertRaisesRegex(ValueError, "PNG_MISSING_OR_SYMLINK"):
            report(symlink, engine="github-runner-cpu", preset="orchard", steps=8)

    def test_report_fields_are_json_serializable(self):
        report_data = report(self.image, engine="github-runner-cpu",
                             preset="greenhouse", steps=12)
        self.assertEqual(json.loads(json.dumps(report_data))["quality_state"],
                         "EXPERIMENTAL_PREVIEW")


if __name__ == "__main__":
    unittest.main()
