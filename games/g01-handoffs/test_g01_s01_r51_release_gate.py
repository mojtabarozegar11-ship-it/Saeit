import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
P=Path(__file__).with_name('g01_s01_r51_release_gate.py')
spec=importlib.util.spec_from_file_location('release_gate',P)
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
class ReleaseGateTests(unittest.TestCase):
 def archive(self,mutation=None):
  assets={n:b'fixture' for n in gate.REQUIRED if n not in {'preview-manifest.json','moj1-commerce-policy.mjs','index.html'}}
  for i in range(20):assets[f'extra-{i}.txt']=b'fixture'
  assets['moj1-commerce-policy.mjs']=b'checkoutEnabled:false ownerApproved:false verifiedBackend:false contractAddress:null'
  assets['index.html']=b'<script type="module" src="./game.js"></script>'
  import hashlib
  manifest={'format':'ramadan-war-offline-preview-v1','release':'R51','payment_status':'disabled','files':{n:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for n,v in assets.items()}}
  assets['preview-manifest.json']=json.dumps(manifest).encode()
  if mutation:mutation(assets)
  temp=tempfile.TemporaryDirectory();p=Path(temp.name)/'build.zip'
  with zipfile.ZipFile(p,'w') as z:
   for n,v in assets.items():z.writestr('ramadan-war/'+n,v)
  return temp,p
 def test_valid_fixture(self):
  t,p=self.archive();self.addCleanup(t.cleanup);self.assertEqual(gate.check_archive(p),[])
 def test_tampered_runtime_asset(self):
  t,p=self.archive(lambda a:a.__setitem__('game.js',b'tampered'));self.addCleanup(t.cleanup)
  self.assertTrue(any('hash mismatch game.js' in s for s in gate.check_archive(p)))
 def test_missing_runtime_asset(self):
  t,p=self.archive(lambda a:a.pop('engine3d.js'));self.addCleanup(t.cleanup)
  self.assertTrue(any('missing engine3d.js' in s for s in gate.check_archive(p)))
 def test_remote_script_blocked(self):
  t,p=self.archive(lambda a:a.__setitem__('index.html',b'<script src="https://evil.invalid/a.js"></script>'));self.addCleanup(t.cleanup)
  self.assertTrue(any('remote executable script' in s for s in gate.check_archive(p)))
 def test_moj1_enabled_blocked(self):
  t,p=self.archive(lambda a:a.__setitem__('moj1-commerce-policy.mjs',b'checkoutEnabled:true'));self.addCleanup(t.cleanup)
  self.assertTrue(any('MOJ1 guard absent' in s for s in gate.check_archive(p)))
 def test_wrong_manifest_format(self):
  t,p=self.archive(lambda a:a.__setitem__('preview-manifest.json',b'{"release":"R51","payment_status":"disabled","files":{}}'));self.addCleanup(t.cleanup)
  self.assertTrue(any('manifest format' in s for s in gate.check_archive(p)))
 def test_entry_count_limit(self):
  def extra(a):
   for i in range(270):a[f'junk-{i}']=b'junk'
  t,p=self.archive(extra);self.addCleanup(t.cleanup)
  self.assertTrue(any('too many ZIP entries' in s for s in gate.check_archive(p)))
 def test_uncompressed_limit(self):
  t,p=self.archive(lambda a:a.__setitem__('huge.bin',b'x'*(81*1024*1024)));self.addCleanup(t.cleanup)
  self.assertTrue(any('uncompressed limit' in s for s in gate.check_archive(p)))
if __name__=='__main__':unittest.main()
