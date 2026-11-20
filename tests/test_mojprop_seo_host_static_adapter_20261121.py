"""Host adapter security regressions using only temporary local fixtures."""
import os
import pwd
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts import mojprop_seo_host_static_adapter_20261121 as m


class AdapterFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p=Path(self.tmp.name)
        self.root=p/"site"
        self.private=p/"private"
        self.stage=self.private/"stage"
        self.root.mkdir(mode=0o700)
        self.private.mkdir(mode=0o700)
        self.stage.mkdir(mode=0o700)
        self.base={x:("baseline-"+x).encode() for x in m.PINS}
        self.candidates={x:("candidate-"+x).encode() if x in m.CHANGED else y for x,y in self.base.items()}
        self.protected={x:("protected-"+x).encode() for x in m.PROTECTED}
        self.pins={x:(m.digest(y),m.digest(self.candidates[x])) for x,y in self.base.items()}
        self.protected_pins={x:m.digest(y) for x,y in self.protected.items()}
        for x,y in {**self.base,**self.protected}.items():self._put(self.root/x,y,private=False)
        for x,y in self.base.items():self._put(self.private/"original"/x,y)
        for x,y in self.base.items():self._put(self.stage/"baseline"/x,y)
        for x,y in self.candidates.items():self._put(self.stage/"candidate"/x,y)
        self.h=m.ExactStaticHost(root=self.root,private=self.private,stage=self.stage,
                 account=pwd.getpwuid(os.geteuid()).pw_name)

    @staticmethod
    def _put(p,data,private=True):
        p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        p.write_bytes(data)
        os.chmod(p,0o600 if private else 0o644)

    def _patch(self):
        from contextlib import ExitStack
        stack=ExitStack()
        stack.enter_context(patch.object(m,"PINS",self.pins))
        stack.enter_context(patch.object(m,"PROTECTED",self.protected_pins))
        stack.enter_context(patch.object(m,"build_v3",return_value=(self.candidates,{})))
        return stack

    def test_readonly_fixture_preflight_checks_five_plus_two(self):
        with self._patch():
            result=self.h.preflight(public=False)
        self.assertEqual(result["exact_pages"],5)
        self.assertEqual(len(result["protected_pages"]),2)
        self.assertFalse(result["production_release_authorized"])
        self.assertFalse(result["all_writers_lock_verified"])

    def test_catalog_candidate_and_backup_are_exact(self):
        with self._patch():
            self.assertEqual(self.h.read_backup("catalog/index.html"),self.base["catalog/index.html"])
            self.assertEqual(self.h.read_candidate("catalog/index.html"),self.candidates["catalog/index.html"])

    def test_missing_protected_signal_parity_is_refused(self):
        self._put(self.root/"signals/index.html",b"unexpected",private=False)
        with self._patch(),self.assertRaises(m.HostSafetyError):
            self.h.preflight(public=False)

    def test_private_backup_exposed_permissions_are_refused(self):
        file=self.stage/"baseline/index.html"
        os.chmod(file,0o644)
        with self._patch(),self.assertRaises(m.HostSafetyError):
            self.h.preflight(public=False)

    def test_symlink_file_and_parent_are_refused(self):
        path=self.root/"signals/index.html"
        path.unlink()
        path.symlink_to(self.root/"index.html")
        with self.assertRaises(m.HostSafetyError):
            self.h.read_live("signals/index.html")
        catalog=self.root/"catalog"
        (catalog/"index.html").unlink()
        catalog.rmdir()
        catalog.symlink_to(self.stage/"candidate/catalog",target_is_directory=True)
        with self.assertRaises(m.HostSafetyError):
            self.h.read_live("catalog/index.html")

    def test_out_of_scope_relative_path_cannot_be_read_or_written(self):
        with self.assertRaises(m.HostSafetyError):self.h.read_live("../index.html")
        with self.assertRaises(m.HostSafetyError):self.h.read_backup("signals/index.html")
        with self.assertRaises(m.HostSafetyError):self.h.replace_exact("signals/index.html","0"*64,b"x")

    def test_atomic_write_callback_rejects_wrong_or_unreviewed_transition(self):
        with self._patch(),patch.object(m,"atomic_replace") as atomic:
            self.h.replace_exact("index.html",self.pins["index.html"][0],self.candidates["index.html"])
            atomic.assert_called_once()
            with self.assertRaises(m.HostSafetyError):
                self.h.replace_exact("index.html","b"*64,self.candidates["index.html"])
            with self.assertRaises(m.HostSafetyError):
                self.h.replace_exact("index.html",self.pins["index.html"][0],b"unreviewed")
            atomic.assert_called_once()

    def test_exclusive_local_lock_is_owned_and_private(self):
        with self.h.local_lock():
            lock=self.private/".mojprop-three-html.lock"
            st=lock.lstat()
            self.assertTrue(stat.S_ISREG(st.st_mode))
            self.assertEqual(st.st_uid,os.geteuid())
            self.assertFalse(st.st_mode&0o077)
            with self.assertRaises(BlockingIOError):
                with self.h.local_lock():pass

    def test_https_redirect_is_refused(self):
        res=MagicMock()
        res.__enter__.return_value=res
        res.status=200
        res.geturl.return_value="https://another.example/page"
        opener=MagicMock()
        opener.open.return_value=res
        with patch.object(m.request,"build_opener",return_value=opener):
            with self.assertRaises(m.HostSafetyError):self.h.read_public("index.html")

    def test_world_writable_target_dir_is_refused(self):
        os.chmod(self.root/"catalog",0o777)
        with self.assertRaises(m.HostSafetyError):
            self.h.read_live("catalog/index.html")


if __name__=="__main__":
    unittest.main()
