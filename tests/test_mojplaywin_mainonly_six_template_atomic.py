"""Synthetic safety tests for exact six main-site template-only publisher."""
import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import mojplaywin_mainonly_six_template_atomic as m

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

class MainOnlySixPublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        base=Path(self.tmp.name)
        app=base/"Saeit-staging"
        root=app/"core/templates/mojplaywin"
        root.mkdir(parents=True,mode=0o700)
        backups=base/"private-backups"
        self.original={}
        self.payload={"classification":"MPW_EXACT_MAINONLY_SIX","files":{}}
        for name in m.NAMES:
            old=None if name.startswith(("founder_signature","unified_visual_tokens")) else b"{% old original template %}"
            if old is not None:
                (root/name).write_bytes(old)
                self.original[name]=old
            new=("{% load static %}"+name+" TEST ONLY").encode()
            self.payload["files"][name]={"old_sha256":sha(old) if old else None,
                "new_sha256":sha(new),"new_b64":base64.b64encode(new).decode()}
        self.root=root
        self.p1=patch.object(m,"APP",app)
        self.p2=patch.object(m,"TEMPLATES",root)
        self.p3=patch.object(m,"BACKROOT",backups)
        self.p1.start();self.p2.start();self.p3.start()

    def tearDown(self):
        self.p3.stop();self.p2.stop();self.p1.stop()
        self.tmp.cleanup()

    def test_exact_deploy_and_checksum_verified_rollback(self):
        m.deploy("39099999999",self.payload)
        for name in m.NAMES:
            self.assertTrue((self.root/name).is_file())
        m.rollback("39099999999")
        for name in m.NAMES:
            if name in self.original:
                self.assertEqual((self.root/name).read_bytes(),self.original[name])
            else:self.assertFalse((self.root/name).exists())

    def test_refuse_changed_preimage_and_do_not_modify_anything(self):
        (self.root/"home.html").write_bytes(b"independent live edit")
        with self.assertRaises(RuntimeError):
            m.deploy("39099999998",self.payload)
        self.assertEqual((self.root/"home.html").read_bytes(),b"independent live edit")
        self.assertFalse((self.root/"founder_signature.html").exists())

    def test_refuse_extra_paths(self):
        self.payload["files"]["core/templates/base.html"]=self.payload["files"]["home.html"]
        with self.assertRaises(RuntimeError):
            m.deploy("39099999997",self.payload)
        self.assertFalse((self.root/"founder_signature.html").exists())

if __name__=="__main__":
    unittest.main()
