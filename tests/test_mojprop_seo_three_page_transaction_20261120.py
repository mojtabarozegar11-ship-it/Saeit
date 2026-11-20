"""Transaction core failure injection, strictly in-memory (no production adapter)."""
import contextlib
import unittest
from unittest.mock import patch
from scripts import mojprop_seo_three_page_transaction_20261120 as m

class ThreePageTransactionTests(unittest.TestCase):
    def setUp(self):
        self.sha="a"*40
        self.flags={k:"true" for k in m.REQUIRED_ATTESTATIONS[:3]}
        self.flags[m.REQUIRED_ATTESTATIONS[3]]=self.sha
        self.before={p:("before:"+p).encode() for p in m.PINS}
        self.candidate={p:("after:"+p).encode() if p in m.CHANGED else b for p,b in self.before.items()}
        self.protected={p:("protected:"+p).encode() for p in m.PROTECTED}
        self.live={**self.before,**self.protected}
        self.pins={p:(m.digest(b),m.digest(self.candidate[p])) for p,b in self.before.items()}
        self.protected_pins={p:m.digest(b) for p,b in self.protected.items()}
        self.writes=[]
        self.locked=False
        self.fail_path=None
        self.fail_after=False
        self.public_bad=False

    @contextlib.contextmanager
    def lock(self):
        self.locked=True
        try:yield
        finally:self.locked=False

    def replace(self,p,expected,data):
        self.assertTrue(self.locked)
        self.assertIn(p,m.CHANGED)
        self.assertEqual(m.digest(self.live[p]),expected)
        if p==self.fail_path and not self.fail_after and data==self.candidate[p]:
            raise OSError("injected before swap")
        self.live[p]=data
        self.writes.append(p)
        if p==self.fail_path and self.fail_after and data==self.candidate[p]:
            raise OSError("injected after swap")

    def read_public(self,p):
        if self.public_bad and self.live[p]!=self.before.get(p,self.protected.get(p)) and p=="index.html":
            return b"unexpected public response"
        return self.live[p]

    def run_transaction(self,**overrides):
        kwargs=dict(attestations=self.flags,release_sha=self.sha,owner_approved=True,
            historical=self.before,baseline=self.before,candidate=self.candidate,
            read_live=self.live.__getitem__,read_public=self.read_public,
            read_backup=self.before.__getitem__,replace_exact=self.replace,exclusive_lock=self.lock)
        kwargs.update(overrides)
        with patch.object(m,"PINS",self.pins),patch.object(m,"PROTECTED",self.protected_pins),patch.object(m,"build_v3",return_value=(self.candidate,{})):
            return m.transaction(**kwargs)

    def test_success_exact_three_writes(self):
        receipt=self.run_transaction()
        self.assertEqual(self.writes,list(m.CHANGED))
        self.assertTrue(receipt["public_verified"])
        self.assertEqual(self.live,{**self.candidate,**self.protected})

    def test_missing_attestation_and_approval_stop_before_writes(self):
        for k in self.flags:
            with self.subTest(key=k),self.assertRaises(PermissionError):
                self.run_transaction(attestations={x:y for x,y in self.flags.items() if x!=k})
        with self.assertRaises(PermissionError):self.run_transaction(owner_approved=False)
        self.assertEqual(self.writes,[])

    def test_drift_and_bad_backup_stop_before_writes(self):
        self.live["index.html"]=b"unreviewed"
        with self.assertRaises(ValueError):self.run_transaction()
        self.live=dict(self.before,**self.protected)
        with self.assertRaises(ValueError):self.run_transaction(read_backup=lambda _:b"invalid")
        self.assertEqual(self.writes,[])

    def test_failure_before_and_after_each_swap_rolls_back(self):
        for path in m.CHANGED:
            for after in (False,True):
                with self.subTest(path=path,after=after):
                    self.fail_path=path;self.fail_after=after
                    with self.assertRaisesRegex(RuntimeError,"EXACT_ROLLBACK_VERIFIED"):self.run_transaction()
                    self.assertEqual(self.live,{**self.before,**self.protected})

    def test_public_mismatch_rolls_back(self):
        self.public_bad=True
        with self.assertRaisesRegex(RuntimeError,"EXACT_ROLLBACK_VERIFIED"):self.run_transaction()
        self.assertEqual(self.live,{**self.before,**self.protected})
