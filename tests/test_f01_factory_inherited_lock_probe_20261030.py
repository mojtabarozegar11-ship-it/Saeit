import unittest
from scripts.f01_factory_inherited_lock_probe_20261030 import describe

class InheritedLockProbeTests(unittest.TestCase):
    def test_init_parent_lock_inheritance(self):
        o=describe(True,True,True,"/tmp/lock","/tmp/lock")
        self.assertTrue(o["init_parent_shell"])
        self.assertTrue(o["inherits_dispatch_fd9"])
        self.assertTrue(o["init_parent_dispatch_fd9"])

    def test_same_name_not_proof_of_lock(self):
        o=describe(True,True,True,"/tmp/unrelated","/tmp/lock")
        self.assertFalse(o["inherits_dispatch_fd9"])
        self.assertTrue(o["init_parent_shell"])

    def test_non_factory_or_other_fd_not_counted(self):
        self.assertFalse(describe(False,True,True,"/tmp/lock","/tmp/lock")["factory"])
        self.assertFalse(describe(False,True,True,"/tmp/lock","/tmp/lock")["inherits_dispatch_fd9"])

    def test_non_init_lock_held_is_not_counted_as_orphan(self):
        o=describe(True,False,True,"/tmp/lock","/tmp/lock")
        self.assertTrue(o["inherits_dispatch_fd9"])
        self.assertFalse(o["init_parent_dispatch_fd9"])

if __name__=="__main__":
    unittest.main()
