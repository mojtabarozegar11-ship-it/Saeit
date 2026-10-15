"""Tests that both the PNG and its no-sale provenance are inseparable."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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

from verify_artifact_pair import ArtifactIntegrityError, verify_pair


@unittest.skipIf(Image is None, "Pillow tests run in dedicated ComfyUI QA CI")
class ArtifactIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.png = Path(self.tmp.name) / "preview.png"
        self.qa = Path(self.tmp.name) / "quality_report.json"
        im = Image.new("RGB", (256, 256))
        p = im.load()
        for y in range(256):
            for x in range(256):
                p[x,y] = ((x + y * 3) % 256, (x * 7 + y * 2) % 256, (x * 5) % 256)
        im.save(self.png, "PNG")
        self.valid = report(self.png, engine="vps-comfyui-sse2", preset="orchard", steps=2, run_id="10203")
        self.qa.write_text(json.dumps(self.valid), encoding="utf-8")

    def update(self, **changes):
        doc = copy.deepcopy(self.valid)
        doc.update(changes)
        self.qa.write_text(json.dumps(doc), encoding="utf-8")

    def test_valid_pair_keeps_store_blocked(self):
        valid = verify_pair(self.png, self.qa, expected_engine="vps-comfyui-sse2")
        self.assertTrue(valid["preview_valid"])
        self.assertFalse(valid["publish_allowed"])
        self.assertFalse(valid["commercial_ready"])

    def test_change_one_pixel_breaks_hash_binding(self):
        with Image.open(self.png) as image:
            pixel = image.getpixel((0, 0))
            image.putpixel((0, 0), tuple(255 - value for value in pixel))
            image.save(self.png, "PNG")
        with self.assertRaisesRegex(
            ArtifactIntegrityError,
            "PNG_SHA256_MISMATCH|IMAGE_BYTE_COUNT_MISMATCH",
        ):
            verify_pair(self.png, self.qa)

    def test_modified_report_approval_is_rejected(self):
        for name, value in (("commercial_ready", True),("publish_allowed", True),
                            ("auto_store_upload_allowed", True),("manual_review_required", False)):
            with self.subTest(name=name):
                self.update(**{name: value})
                with self.assertRaises(ArtifactIntegrityError):
                    verify_pair(self.png, self.qa)

    def test_wrong_engine_and_source_rejected(self):
        with self.assertRaisesRegex(ArtifactIntegrityError, "UNTRUSTED_ENGINE"):
            verify_pair(self.png, self.qa, expected_engine="github-runner-cpu")
        self.update(source={"engine": "fake", "preset":"orchard", "steps":2})
        with self.assertRaisesRegex(ArtifactIntegrityError, "UNTRUSTED_ENGINE"):
            verify_pair(self.png, self.qa)

    def test_invalid_report_rejected(self):
        self.qa.write_text("{",encoding="utf-8")
        with self.assertRaisesRegex(ArtifactIntegrityError, "INVALID_JSON_REPORT"):
            verify_pair(self.png, self.qa)

    def test_missing_block_reason_rejected(self):
        self.update(block_reasons=[])
        with self.assertRaisesRegex(ArtifactIntegrityError, "BLOCK_REASON_MISSING"):
            verify_pair(self.png, self.qa)

    def test_symlinks_rejected(self):
        link = Path(self.tmp.name) / "linked.png"
        link.symlink_to(self.png)
        with self.assertRaisesRegex(ArtifactIntegrityError, "SYMLINK_NOT_ACCEPTED"):
            verify_pair(link, self.qa)


if __name__ == "__main__":
    unittest.main()
