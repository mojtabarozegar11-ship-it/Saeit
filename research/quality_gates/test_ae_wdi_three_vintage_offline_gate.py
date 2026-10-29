"""Synthetic ZIP fixtures ONLY; never real WDI historical observations."""
import hashlib
import json
import pathlib
import tempfile
import unittest
import zipfile
from ae_wdi_three_vintage_offline_gate import OFFICIAL, FINAL_OFFICIAL, EvidenceGateError, verify

class WdiArchiveGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.releases = []
        for idx, (release, url) in enumerate(OFFICIAL.items()):
            p = self.root / ("fixture_" + str(idx) + ".zip")
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("fixture.xlsx", b"NOT_A_REAL_WDI_WORKBOOK")
            self.releases.append({"id":release, "source_url":url, "resolved_url":FINAL_OFFICIAL[release], "path":p.name,
                "sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
                "bytes":p.stat().st_size, "retrieved_utc":"2026-10-29T00:00:00Z"})
    def manifest(self):
        p = self.root / "manifest.json"
        p.write_text(json.dumps({"releases":self.releases}), encoding="utf-8")
        return p
    def test_synthetic_zip_integrity_only(self):
        result = verify(self.manifest())
        self.assertEqual(result["state"], "ARCHIVE_INTEGRITY_ONLY_NOT_HISTORICAL_BENCHMARK")
        self.assertEqual(len(result["releases"]), 3)
    def test_mismatched_final_url_fails_closed(self):
        self.releases[0]["resolved_url"] = "https://untrusted.example/WDI_excel_2024_12_16.zip"
        with self.assertRaisesRegex(EvidenceGateError, "redirect/final URL mismatch"):
            verify(self.manifest())
    def test_missing_final_url_fails_closed(self):
        del self.releases[1]["resolved_url"]
        with self.assertRaisesRegex(EvidenceGateError, "redirect/final URL mismatch"):
            verify(self.manifest())
    def test_sha_mismatch_fails_closed(self):
        self.releases[0]["sha256"] = "0"*64
        with self.assertRaisesRegex(EvidenceGateError, "SHA-256 mismatch"):
            verify(self.manifest())
    def test_duplicate_release_fails_closed(self):
        self.releases[2]["id"] = self.releases[1]["id"]
        with self.assertRaisesRegex(EvidenceGateError, "release"):
            verify(self.manifest())
    def test_path_traversal_zip_fails_closed(self):
        p = self.root / self.releases[0]["path"]
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("../fixture.xlsx", b"NOT_WDI")
        self.releases[0]["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
        self.releases[0]["bytes"] = p.stat().st_size
        with self.assertRaisesRegex(EvidenceGateError, "Unsafe ZIP"):
            verify(self.manifest())

if __name__ == "__main__":
    unittest.main()
