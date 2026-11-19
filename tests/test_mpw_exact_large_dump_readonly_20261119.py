import os
from pathlib import Path
import tempfile
import unittest
from scripts.mpw_exact_large_dump_readonly_20261119 import (
    token, find_exact, inspect_markers, bounded_sample, SAMPLE
)

class ExactDumpTests(unittest.TestCase):
    def test_markers_are_booleans_and_no_raw_sql(self):
        r=inspect_markers(b"-- MariaDB dump\nCREATE DATABASE private_name",b"secret row\n-- Dump completed on 2026-11-19\n")
        self.assertTrue(r["sql_header_marker"])
        self.assertTrue(r["database_ddl_marker"])
        self.assertTrue(r["sql_completion_marker"])
        self.assertNotIn("private_name",str(r))
        self.assertNotIn("secret row",str(r))
    def test_truncated_dump_is_not_marked_complete(self):
        r=inspect_markers(b"-- MySQL dump",b"unfinished row")
        self.assertFalse(r["sql_completion_marker"])
        self.assertFalse(r["tail_ends_newline"])
    def test_exact_identity_not_size_alone(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve()
            backups=root/"backups"
            backups.mkdir()
            p=backups/"original.sql"
            q=backups/"different.sql"
            for f in (p,q):
                f.write_bytes(b"abcd")
                os.utime(f,(12345,12345))
            (backups/"alias.sql").symlink_to(p)
            matches,complete=find_exact(backups,root,token("backups/original.sql"),size=4,mtime=12345)
            self.assertTrue(complete)
            self.assertEqual([x[0] for x in matches],[p])
    def test_budget_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve()
            (root/"x").write_bytes(b"x")
            matches,complete=find_exact(root,root,"missing",size=1,mtime=0,seconds=-1)
            self.assertFalse(complete)
            self.assertEqual(matches,[])
    @unittest.skipUnless(hasattr(os,"O_NOATIME") and hasattr(os,"O_NOFOLLOW"),"Linux flags required")
    def test_sample_does_not_change_file_or_log_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"dump.sql"
            original=b"-- MySQL dump\n"+b"x"*(2*SAMPLE)+b"\n-- Dump completed on 2026-11-19\n"
            p.write_bytes(original)
            s=p.stat()
            result=bounded_sample(p,s)
            self.assertTrue(result["sample_available"])
            self.assertTrue(result["sql_completion_marker"])
            self.assertEqual(p.stat().st_atime_ns,s.st_atime_ns)
            self.assertEqual(p.stat().st_mtime_ns,s.st_mtime_ns)
            self.assertEqual(p.read_bytes(),original)
    @unittest.skipUnless(hasattr(os,"O_NOATIME") and hasattr(os,"O_NOFOLLOW"),"Linux flags required")
    def test_changed_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"dump.sql"
            p.write_bytes(b"old")
            s=p.stat()
            p.write_bytes(b"new larger")
            with self.assertRaises(ValueError):
                bounded_sample(p,s)
