"""Regression tests for real private agricultural research navigator ZIP artifacts."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
import zipfile

TARGET=Path(__file__).resolve().parents[1]/"scripts/factory_agri200_downloadable_20261023.py"
spec=importlib.util.spec_from_file_location("agri_downloadable",str(TARGET))
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class DownloadableCandidateTests(unittest.TestCase):
    def setup_data(self):
        design={"chapters":[{"unit":i,"title_fa":f"فصل آزمایشی {i}",
                             "title_en":f"Sample unit {i}","source_ids":["S1"]}
                            for i in range(1,6)]}
        research={"sources":[{"id":f"S{i}","title":f"Indexed paper {i}",
                              "publisher":f"University {i}","url":f"https://example{i}.org/paper",
                              "publication_year":2024,"doi":f"10.1000/{i}"}
                             for i in range(1,5)]}
        editions={"fa-IR":{"title":"راهنمای گیاه"},
                  "en-US":{"title":"Plant Research Guide"}}
        return design,research,editions

    def test_offline_html_contains_real_interaction_and_source_links(self):
        h=mod.render_navigator(*self.setup_data(),"WO-00000001")
        self.assertIn("text/csv",h)
        self.assertIn("window.print()",h)
        self.assertIn('lang="fa"',h)
        self.assertIn("Plant Research Guide",h)
        self.assertIn("Indexed paper 4",h)
        self.assertIn("source",h)

    def test_html_script_injection_is_inert(self):
        d,r,e=self.setup_data()
        e["en-US"]["title"]='</script><img src=x onerror=alert(1)>'
        h=mod.render_navigator(d,r,e,"WO-00000001")
        self.assertNotIn('</script><img',h)
        self.assertIn("\\u003c/script\\u003e",h)
        self.assertEqual(h.count("</script>"),2)

    def test_distinct_zips_are_deterministic_and_unzip_cleanly(self):
        files={"index.html":b"<html>usable</html>","README.md":b"test product"}
        first=mod.reproducible_zip(files,"agri-WO-00000001--r001")
        second=mod.reproducible_zip(files,"agri-WO-00000001--r001")
        self.assertEqual(first,second)
        self.assertEqual(mod.digest(first),mod.digest(second))
        with zipfile.ZipFile(io.BytesIO(first)) as z:
            self.assertEqual(z.testzip(),None)
            self.assertEqual(z.read("agri-WO-00000001--r001/README.md"),b"test product")

    def test_rejects_unsafe_archive_members(self):
        with self.assertRaisesRegex(RuntimeError,"UNSAFE_MEMBER"):
            mod.reproducible_zip({"../evil":b"data"},"agri-WO-00000001--r001")
        with self.assertRaisesRegex(RuntimeError,"UNSAFE_PAYLOAD"):
            mod.reproducible_zip({"readme.md":b""},"agri-WO-00000001--r001")

    def test_no_insufficient_source_or_chapter_evidence(self):
        d,r,e=self.setup_data()
        with self.assertRaisesRegex(RuntimeError,"INSUFFICIENT_EVIDENCE"):
            mod.render_navigator(d,{"sources":r["sources"][:3]},e,"WO-00000001")
        with self.assertRaisesRegex(RuntimeError,"INSUFFICIENT_EVIDENCE"):
            mod.render_navigator({"chapters":d["chapters"][:4]},r,e,"WO-00000001")

    def test_semantic_no_commercial_clearance(self):
        src=TARGET.read_text(encoding="utf-8")
        for value in ('"scientific_quality_certified":False',
                      '"ready_for_paid_store":False',
                      '"public_distribution_allowed":False',
                      '"paid_publications_created":0'):
            self.assertIn(value,src)

if __name__=="__main__":
    unittest.main()
