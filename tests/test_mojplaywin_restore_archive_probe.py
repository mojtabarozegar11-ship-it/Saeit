"""Read-only, privacy-safe archive metadata diagnostics on synthetic streams only."""
import io
import tarfile
import unittest
from scripts.mojplaywin_restore_archive_probe import MARKER, probe

def stream(items):
    out = io.BytesIO()
    with tarfile.open(fileobj=out,mode="w") as tar:
        for name,kind,link in items:
            member = tarfile.TarInfo(name)
            if kind == "file":
                member.size = 5
                tar.addfile(member,io.BytesIO(b"HELLO"))
            elif kind == "symlink":
                member.type = tarfile.SYMTYPE
                member.linkname=link
                tar.addfile(member)
            elif kind == "directory":
                member.type = tarfile.DIRTYPE
                tar.addfile(member)
    return io.BytesIO(out.getvalue()+MARKER)

class ArchiveProbeTests(unittest.TestCase):
    def test_safe_ordinary_archive(self):
        r = probe(stream([
          ("Saeit-staging/","directory",None),
          ("Saeit-staging/code.py","file",None),
          ("mojplaywin.com/page.html","file",None),
        ]))
        self.assertEqual(r["entry_count"],3)
        self.assertEqual(r["first_issue"],"none_detected")
        self.assertTrue(r["source_completion_footer_seen"])
        self.assertFalse(r["release_permitted"])

    def test_report_only_category_for_unsafe_links_and_escape(self):
        r=probe(stream([
          ("Saeit-staging/code.py","file",None),
          ("mojplaywin.com/secret-link","symlink","/home/private-token-never-log"),
          ("mojplaywin.com/escape","symlink","../../private-token-never-log"),
        ]))
        self.assertIn("link_absolute",r["issue_counts"])
        self.assertIn("link_traversal",r["issue_counts"])
        self.assertNotIn("private-token",str(r))
        self.assertFalse(r["isolated_restore_completed"])

    def test_reject_duplicate_and_missing_footer(self):
        raw=stream([("mojplaywin.com/a","file",None),("mojplaywin.com/a","file",None)]).getvalue()
        r=probe(io.BytesIO(raw[:-len(MARKER)]))
        self.assertEqual(r["counts"]["duplicates"],1)
        self.assertIn("source_completion_footer_missing",r["issue_counts"])

if __name__=="__main__":
    unittest.main()
