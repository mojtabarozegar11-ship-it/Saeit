"""Safe synthetic quarantine tests, never use live backups or linked external paths."""
import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.mojplaywin_quarantined_files_test import recover

def make_archive(link_count=3):
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode="w") as tar:
        for name in ("Saeit-staging/app.py","mojplaywin.com/index.html"):
            data=b"safe-fixture"
            item=tarfile.TarInfo(name)
            item.size=len(data)
            tar.addfile(item,io.BytesIO(data))
        for i in range(link_count):
            item=tarfile.TarInfo("Saeit-staging/fixture-link-"+str(i))
            item.type=tarfile.SYMTYPE
            item.linkname="/not-a-real-allowed-destination/"+str(i)
            tar.addfile(item)
    out.seek(0)
    return out

class QuarantinedFilesTest(unittest.TestCase):
    def test_exact_three_links_quarantined_never_created(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"private"
            root.mkdir(mode=0o700)
            report=recover(make_archive(3),root)
            self.assertTrue(report["ordinary_content_restored"])
            self.assertFalse(report["restore_complete"])
            self.assertEqual(report["absolute_links_quarantined"],3)
            self.assertEqual(report["regular_files_restored"],2)
            self.assertEqual(report["root_count_restored"],2)
            self.assertFalse(report["production_modified"])
            self.assertEqual((root/"Saeit-staging/app.py").read_bytes(),b"safe-fixture")
            for i in range(3):
                p=root/("Saeit-staging/fixture-link-"+str(i))
                self.assertFalse(p.exists())
                self.assertFalse(p.is_symlink())

    def test_wrong_link_count_fails_closed(self):
        for count in (0,2,4):
            with self.subTest(count=count):
                with tempfile.TemporaryDirectory() as td:
                    root=Path(td)/"private"
                    root.mkdir(mode=0o700)
                    with self.assertRaises(ValueError):
                        recover(make_archive(count),root)

if __name__=="__main__":
    unittest.main()
