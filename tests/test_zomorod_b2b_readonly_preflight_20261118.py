import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from scripts.zomorod_b2b_readonly_preflight_20261118 import state,inventory,STATIC,SOURCES

class ReadonlyB2BTests(unittest.TestCase):
    def test_fixed_public_and_source_paths_only(self):
        for x in STATIC+SOURCES:
            self.assertNotIn("..",Path(x).parts)
            for bad in (".env",".ssh","sqlite3","private","customer"):
                self.assertNotIn(bad,x.lower())
    def test_empty_root_is_not_a_positive(self):
        with tempfile.TemporaryDirectory() as d:
            x=inventory(Path(d),False)
            self.assertFalse(x["http_verified"])
            self.assertFalse(x["backup_verified"])
            self.assertFalse(x["possible_static_company_shadow"])
    def test_static_shadow_is_only_a_risk(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"public_html"/"company"
            p.mkdir(parents=True)
            (p/"index.html").write_text("public")
            x=inventory(Path(d),False)
            self.assertTrue(x["possible_static_company_shadow"])
            self.assertFalse(x["passenger_route_verified"])
            self.assertFalse(x["release_performed"])
    def test_symlink_unsafe(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)
            (r/"outside").mkdir()
            (r/"public_html").symlink_to(r/"outside",target_is_directory=True)
            self.assertEqual(state(r,"public_html/index.html"),"unsafe")
    def test_no_content_open(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(Path,"open",side_effect=AssertionError("No content reads")):
                self.assertTrue(inventory(Path(d),False)["read_only"])
    def test_wrong_owner_denied(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PermissionError):
                inventory(Path(d),True)

if __name__=="__main__": unittest.main()
