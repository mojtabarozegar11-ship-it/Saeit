import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import f01_zip_reproducibility_gate as gate  # noqa: E402


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def build(directory, payload=b"# Farm economics\n"):
    directory.mkdir()
    filename = "README.md"
    checksum = hashlib.sha256()
    checksum.update(filename.encode("utf-8") + b"\x00")
    checksum.update(payload)
    archive_path = directory / gate.ZIP_NAME
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo(gate.RECIPE + "/" + filename, date_time=(2020, 1, 1, 0, 0, 0))
        info.external_attr = 0o100644 << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, payload)
    zip_bytes = archive_path.read_bytes()
    manifest = {
        "recipe": gate.RECIPE, "files": [filename],
        "source_sha256": checksum.hexdigest(), "artifact_sha256": digest(zip_bytes),
        "bytes": len(zip_bytes), "qa_status": "passed",
        "qa_measurements": {"successful_tests": 47, "failures": 0, "errors": 0,
                            "skipped": 0, "unexpected_successes": 0},
        "commercial_status": "private_internal_qa_pass_not_published",
        "professional_quality_approved": False, "professional_quality_score": None,
        "public_listing_enabled": False,
    }
    (directory / "manufacturing_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8")


class F01ReproducibilityGateTests(unittest.TestCase):
    def test_separate_identical_builds_pass_with_release_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / "first", Path(temp) / "second"
            build(first)
            build(second)
            receipt = gate.verify_reproducibility(first, second)
            self.assertTrue(receipt["reproducible_zip"])
            self.assertFalse(receipt["commercial_release_allowed"])
            self.assertIsNone(receipt["professional_quality_points"])

    def test_mismatched_payload_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / "first", Path(temp) / "second"
            build(first)
            build(second, b"# Different\n")
            with self.assertRaisesRegex(ValueError, "NONREPRODUCIBLE_BUILD"):
                gate.verify_reproducibility(first, second)

    def test_modified_archive_fails_even_when_manifest_unmodified(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / "first", Path(temp) / "second"
            build(first)
            build(second)
            with (second / gate.ZIP_NAME).open("ab") as stream:
                stream.write(b"changed")
            with self.assertRaisesRegex(ValueError, "ARTIFACT_MANIFEST_MISMATCH"):
                gate.verify_reproducibility(first, second)

    def test_same_build_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first"
            build(first)
            with self.assertRaisesRegex(ValueError, "BUILDS_ARE_NOT_SEPARATE"):
                gate.verify_reproducibility(first, first)

    def test_release_approval_must_not_be_inferred(self):
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first"
            build(first)
            manifest_path = first / "manufacturing_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["professional_quality_approved"] = True
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "RELEASE_GATE_NOT_CLOSED"):
                gate.verify_build(first)


if __name__ == "__main__":
    unittest.main()
