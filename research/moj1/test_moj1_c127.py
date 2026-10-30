import hashlib, tempfile, pathlib, unittest
from moj1_c127_nofollow_hash import checked_hash
class T(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
  self.root=pathlib.Path(self.t.name)/'root';self.root.mkdir();(self.root/'a').mkdir();(self.root/'a'/'x').write_bytes(b'abc')
  self.sha=hashlib.sha256(b'abc').hexdigest()
 def test_regular(self):self.assertEqual(checked_hash(self.root,{'path':'a/x','sha256':self.sha}),'a/x')
 def test_bad_digest(self):
  with self.assertRaisesRegex(ValueError,'digest mismatch'):checked_hash(self.root,{'path':'a/x','sha256':'0'*64})
 def test_traversal(self):
  with self.assertRaises(ValueError):checked_hash(self.root,{'path':'a/../x','sha256':self.sha})
 def test_file_symlink(self):
  (self.root/'a'/'link').symlink_to('x')
  with self.assertRaises(ValueError):checked_hash(self.root,{'path':'a/link','sha256':self.sha})
 def test_dir_symlink(self):
  (self.root/'alias').symlink_to('a',target_is_directory=True)
  with self.assertRaises(ValueError):checked_hash(self.root,{'path':'alias/x','sha256':self.sha})
 def test_root_symlink(self):
  p=pathlib.Path(self.t.name)/'alias';p.symlink_to(self.root,target_is_directory=True)
  with self.assertRaises(ValueError):checked_hash(p,{'path':'a/x','sha256':self.sha})
 def test_directory_as_file(self):
  with self.assertRaises(ValueError):checked_hash(self.root,{'path':'a','sha256':self.sha})
 def test_uppercase_digest(self):
  with self.assertRaises(ValueError):checked_hash(self.root,{'path':'a/x','sha256':self.sha.upper()})
if __name__=='__main__':unittest.main()
