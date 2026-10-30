import hashlib
import tempfile
import unittest
from pathlib import Path
from g01_s01_release_preflight_r40 import audit
import json

class GuardTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  (self.root/'index.html').write_text('hello')
  (self.root/'game.js').write_text("import {x} from './backup-clipboard.mjs';")
  (self.root/'backup-clipboard.mjs').write_text('export const x=1')
  self.assets=['index.html','game.js','backup-clipboard.mjs']
  self.deploy='ASSETS='+repr(self.assets)
  self.manifest={'version':'R40','sha256':{x:hashlib.sha256((self.root/x).read_bytes()).hexdigest() for x in self.assets}}
 def tearDown(self):self.tmp.cleanup()
 def check(self):return audit(self.root,self.deploy,json.dumps(self.manifest))
 def test_good(self):self.assertEqual(self.check()['status'],'PASS')
 def test_missing_runtime_import(self):
  self.deploy="ASSETS=['index.html','game.js']"
  self.assertIn('missing-js-import-in-deploy:backup-clipboard.mjs',self.check()['errors'])
 def test_tamper_detected(self):
  (self.root/'game.js').write_text('modified')
  self.assertIn('sha-mismatch:game.js',self.check()['errors'])
 def test_path_escape_rejected(self):
  self.deploy="ASSETS=['../secret','game.js']"
  self.assertIn('unsafe-path:../secret',self.check()['errors'])
 def test_symlink_rejected(self):
  (self.root/'backup-clipboard.mjs').unlink()
  (self.root/'backup-clipboard.mjs').symlink_to(self.root/'index.html')
  self.assertIn('missing-or-symlink:backup-clipboard.mjs',self.check()['errors'])
if __name__=='__main__':unittest.main()
