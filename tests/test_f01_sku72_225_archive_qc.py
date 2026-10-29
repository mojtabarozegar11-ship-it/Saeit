import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

source = Path(__file__).resolve().parents[1] / "scripts/f01_sku72_225_archive_qc.py"
spec = importlib.util.spec_from_file_location("f01_sku_archive_qc", source)
qc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qc)


class ArchiveQCTests(unittest.TestCase):
    def test_good_72_and_225_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "safe.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("README.txt", "independent private archive sample")
                z.writestr("assets/index.html", "<html>test</html>")
            before = p.read_bytes()
            for sku in (72, 225):
                result = qc.verify(sku, p)
                self.assertEqual(result["status"], "ZIP_INTEGRITY_VERIFIED_ONLY")
                self.assertEqual(result["file_count"], 2)
                self.assertFalse(result["content_quality_verified"])
                self.assertFalse(result["store_delivery_verified"])
            self.assertEqual(p.read_bytes(), before)

    def test_sku879_refused_even_with_valid_archive(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "safe.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("file.txt", "x")
            with self.assertRaisesRegex(qc.QCBlocked, "SKU_NOT_AUTHORIZED"):
                qc.verify(879, p)

    def test_path_traversal_and_duplicate_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "unsafe.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("../escape.txt", "x")
            with self.assertRaisesRegex(qc.QCBlocked, "UNSAFE_MEMBER_NAME"):
                qc.verify(72, p)
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("A.txt", "a")
                z.writestr("a.txt", "b")
            with self.assertRaisesRegex(qc.QCBlocked, "DUPLICATE_MEMBER_NAME"):
                qc.verify(225, p)

    def test_expected_hash_mismatch_and_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "safe.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("ok.txt", "safe")
            with self.assertRaisesRegex(qc.QCBlocked, "SHA256_MISMATCH"):
                qc.verify(72, p, "0" * 64)
            alias = Path(d) / "alias.zip"
            alias.symlink_to(p)
            with self.assertRaisesRegex(qc.QCBlocked, "LINKED_PATH"):
                qc.verify(72, alias)

    def test_non_zip_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fake.zip"
            p.write_text("not a zip")
            with self.assertRaisesRegex(qc.QCBlocked, "ZIP_READ_OR_CRC_FAILURE"):
                qc.verify(72, p)


if __name__ == "__main__":
    unittest.main()
