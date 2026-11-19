import os
from pathlib import Path
import tempfile
import unittest
from scripts.mpw_staging_growth_metadata_20261119 import census, classify

class StagingGrowthTests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(classify("DUMP.SQL.GZ"),"sql_dump")
        self.assertEqual(classify("app.sqlite3"),"database_file")
        self.assertEqual(classify("archive.tar.gz"),"archive")
        self.assertEqual(classify("unknown.secret"),"other")
    def test_metadata_only_deduplicates_hardlinks_and_ignores_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve()
            p=root/"private-sensitive-name.sql"
            p.write_bytes(b"x"*8192)
            os.link(p,root/"second.sql")
            (root/"symlink.sql").symlink_to(p)
            r=census(root)
            self.assertTrue(r["complete"])
            self.assertEqual(r["types"]["sql_dump"]["files"],1)
            self.assertEqual(r["hardlinks_deduplicated"],1)
            self.assertEqual(r["symlinks_skipped"],1)
            self.assertNotIn("private-sensitive-name",str(r))
            self.assertFalse(r["safe_to_delete"])
    def test_budget_never_claims_complete(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve()
            (root/"x").write_bytes(b"x")
            self.assertFalse(census(root,max_entries=0)["complete"])
    def test_root_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve()
            (root/"real").mkdir()
            (root/"alias").symlink_to(root/"real",target_is_directory=True)
            with self.assertRaises(ValueError):
                census(root/"alias")
