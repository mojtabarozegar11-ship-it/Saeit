"""Only synthetic fixture bytes: no production archive access."""
import io
import tarfile
import unittest
from tools.moj_commerce_v12_archive_link_blocker import classify, interpreter_rebuildable


def fixture(targets):
    f = io.BytesIO()
    with tarfile.open(fileobj=f, mode="w") as t:
        for root in ("Saeit-staging", "mojplaywin.com"):
            content=b"fixture"
            info=tarfile.TarInfo(root+"/synthetic.txt")
            info.size=len(content)
            t.addfile(info,io.BytesIO(content))
        for idx, target in enumerate(targets):
            item=tarfile.TarInfo("Saeit-staging/.venv/bin/python"+str(idx+3))
            item.type=tarfile.SYMTYPE
            item.linkname=target
            t.addfile(item)
    f.seek(0)
    return f


class LinkClassifierTests(unittest.TestCase):
    def test_allowed_python_executable_is_only_venv_derived(self):
        self.assertTrue(interpreter_rebuildable("Saeit-staging/.venv/bin/python3",
                                                "/usr/bin/python3"))
        self.assertTrue(interpreter_rebuildable("Saeit-staging/venv/bin/python3.11",
                                                "/opt/alt/python311/bin/python3.11"))
        self.assertFalse(interpreter_rebuildable("mojplaywin.com/uploads/python3",
                                                 "/usr/bin/python3"))
        self.assertFalse(interpreter_rebuildable("Saeit-staging/.venv/bin/python3",
                                                 "/home/other/account/key"))

    def test_arbitrary_absolute_symlink_remains_blocked(self):
        result=classify(fixture(["/tmp/private"]))
        self.assertEqual(result["counters"]["absolute_links"],1)
        self.assertEqual(result["counters"]["unsafe_external_links"],1)
        self.assertFalse(result["all_absolute_links_derived_interpreter_dependencies"])
        self.assertFalse(result["release_permitted"])

    def test_safe_regular_files_never_claim_complete_restore(self):
        result=classify(fixture([]))
        self.assertEqual(result["counters"]["regular"],2)
        self.assertTrue(result["verified_archive_roots"])
        self.assertFalse(result["all_absolute_links_derived_interpreter_dependencies"])
        self.assertFalse(result["functional_restore_verified"])
        self.assertFalse(result["release_permitted"])


if __name__=="__main__":
    unittest.main()
