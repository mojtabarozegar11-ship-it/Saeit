import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from g01_s01_release_asset_audit_r35 import audit

class ReleaseAudit(unittest.TestCase):
    def test_valid_local(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'index.html').write_text('<script src="./app.js"></script>');(p/'app.js').write_text('')
            self.assertTrue(audit(p)['passed'])
    def test_missing_asset(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'index.html').write_text('<img src="missing.png">')
            self.assertTrue(any(s.startswith('MISSING:') for s in audit(p)['issues']))
    def test_path_escape(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'index.html').write_text('<script src="../secret.js"></script>')
            self.assertTrue(any(s.startswith('PATH_ESCAPE:') for s in audit(p)['issues']))
    def test_remote_script(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'index.html').write_text('<script src="https://example.org/app.js"></script>')
            self.assertTrue(any(s.startswith('REMOTE_DEPENDENCY:') for s in audit(p)['issues']))
    def test_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'index.html').write_text('ok');(p/'link').symlink_to('/etc/hosts')
            self.assertTrue(any(s.startswith('SYMLINK:') for s in audit(p)['issues']))

if __name__=='__main__':unittest.main()
