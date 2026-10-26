"""Offline QA regression for three immutable MojPlayWin live-product copies."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mpw_live_three_sku_qa_copy_20261023.py"
spec = importlib.util.spec_from_file_location("live_three_qa", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def zip_good():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("README.md", "The product works offline.")
    return b.getvalue()


def bundle(bad_hash=False):
    files = {72: zip_good(), 225: zip_good() + b"\x00", 879: b"%PDF-1.4\nsample"}
    rows = [{"id": i, "title": f"Product {i}", "size": len(files[i]),
             "sha256": hashlib.sha256(files[i]).hexdigest()} for i in mod.IDS]
    if bad_hash:
        rows[-1]["sha256"] = "0" * 64
    manifest = {"schema": mod.SCHEMA, "site": "mojplaywin.com", "products": rows}
    b = io.BytesIO()
    with tarfile.open(fileobj=b, mode="w:gz") as t:
        payload = json.dumps(manifest).encode()
        m = tarfile.TarInfo("manifest.json")
        m.size = len(payload)
        t.addfile(m, io.BytesIO(payload))
        for i in mod.IDS:
            m = tarfile.TarInfo(f"product-{i}.bin")
            m.size = len(files[i])
            t.addfile(m, io.BytesIO(files[i]))
    return io.BytesIO(b.getvalue()), rows


class PrivateThreeTests(unittest.TestCase):
    def test_exact_three_rejects_wrong_identity(self):
        _, rows = bundle()
        with self.assertRaisesRegex(RuntimeError, "EXACT_THREE_REQUIRED"):
            mod.validate_manifest({"schema": mod.SCHEMA, "site": "mojplaywin.com",
                                   "products": rows[:2]})

    def test_real_private_copies_are_sha_bound_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "vps-private"
            src, rows = bundle()
            with contextlib.redirect_stdout(io.StringIO()):
                result = mod.vps_ingest(dest, src)
            self.assertEqual([x["product_id"] for x in result], list(mod.IDS))
            for row in rows:
                copy = dest / "copies" / str(row["id"]) / (row["sha256"] + ".bin")
                request = dest / "review-requests" / str(row["id"]) / (row["sha256"] + ".json")
                self.assertEqual(mod.sha(copy), row["sha256"])
                receipt = json.loads(request.read_text())
                self.assertFalse(receipt["live_replacement_authorized"])
                self.assertFalse(receipt["quality_certified"])
                self.assertTrue(receipt["storefront_unchanged"])
            with contextlib.redirect_stdout(io.StringIO()):
                src.seek(0)
                second = mod.vps_ingest(dest, src)
            self.assertEqual(result, second)

    def test_hash_mismatch_fails_before_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "vps-private"
            with self.assertRaisesRegex(RuntimeError, "COPY_HASH_MISMATCH"):
                mod.vps_ingest(dest, bundle(bad_hash=True)[0])
            self.assertFalse((dest / "copies").exists())

    def test_broken_deflate_is_reported_without_crashing_the_review(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "broken.zip"
            archive_bytes = io.BytesIO()
            with zipfile.ZipFile(archive_bytes, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("notes.txt", "quality review text " * 100)
            raw = bytearray(archive_bytes.getvalue())
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                info = z.infolist()[0]
                first_compressed_byte = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
            raw[first_compressed_byte] = 0xFF
            archive.write_bytes(raw)
            report = mod.technical_review(archive)
            self.assertFalse(report["archive_crc_pass"])
            self.assertTrue(any(s.startswith("ZIP_INTEGRITY_") for s in report["issues"]))

    def test_traversal_inside_zip_is_flagged_not_extracted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("../outside.txt", "not allowed")
            result = mod.technical_review(path)
            self.assertFalse(result["archive_crc_pass"])
            self.assertIn("ZIP_INTEGRITY_ValueError", result["issues"])
            self.assertFalse((Path(directory) / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()
