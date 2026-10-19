"""Only explicitly permitted MojPlayWin main-domain GET pages may pass the bridge."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/mpw_dynamic_main_shell_atomic_20261019.py'
PHP=ROOT/'scripts/mpw_dynamic_main_shell_20261019.php'

class MojPlayWinDynamicOnlySafeguards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('mpw_dynamic_19',SCRIPT)
        cls.module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
    def test_routing_exactly_nineteen_root_paths(self):
        m=self.module
        self.assertEqual(len(m.ROUTES),19)
        self.assertEqual(len(set(m.ROUTES)),19)
        self.assertTrue(all('/' not in p for p in m.ROUTES))
        self.assertIn('store',m.ROUTES)
        self.assertIn('education',m.ROUTES)
        self.assertIn('weather',m.ROUTES)
        self.assertIn('contact',m.ROUTES)
        self.assertIn('support',m.ROUTES)
        self.assertEqual(m.RULES.count('RewriteRule'),1)
        self.assertIn('^GET$',m.RULES)
        self.assertLess(m.RULES.index('QUERY_STRING'),m.RULES.index('REQUEST_URI'))
        self.assertIn('mpw_template_passthru=1',m.RULES)
        for protected in ('taniya','farnaz','saman','zahra','roham','picm'):
            self.assertNotIn(protected,m.RULES)
    def test_source_and_runtime_constraints(self):
        source=PHP.read_text(encoding='utf8')
        self.assertIn("'https://mojplaywin.com'.$path",source)
        self.assertIn('CURLOPT_SSL_VERIFYPEER=>true',source)
        self.assertIn('CURLOPT_SSL_VERIFYHOST=>2',source)
        self.assertIn('CURLOPT_FOLLOWLOCATION=>false',source)
        self.assertIn('Cookie: ',source)
        self.assertIn('set-cookie',source)
        self.assertIn('content-security-policy',source)
        self.assertIn("if (PHP_SAPI==='cli'",source)
        self.assertIn('class="mw-site-nav"',source)
        self.assertIn('class="mw-site-footer"',source)
        self.assertIn('Mojtaba Roozegar',source)
        self.assertNotIn('systemctl restart',source)
        self.assertNotIn('restart.txt',source)
        self.assertNotIn('shell_exec(',source)
        self.assertNotIn('eval(',source)
    def test_py_offline_preflight(self):
        r=subprocess.run([sys.executable,str(SCRIPT),'selftest'],
            capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('MPW_DYNAMIC_MAIN_EXACT19_SELFTEST=PASS',r.stdout)
    def test_shell_no_writes_to_shared_templates(self):
        s=SCRIPT.read_text(encoding='utf8')
        self.assertIn("TARGET=ROOT/'design-preview-20261017/_mpw_dynamic_main_shell_20261019.php'",s)
        self.assertIn("EXPECTED_HT=",s)
        self.assertIn("sha(old)!=EXPECTED_HT",s)
        self.assertIn("def rollback(",s)
        self.assertNotIn("rmtree(",s)
        self.assertNotIn("passenger_wsgi.py').touch",s)
    def test_php_parse_and_html_transform(self):
        import shutil
        php=shutil.which('php')
        if php is None:self.skipTest('PHP CLI is validated again by remote GitHub Actions')
        for args,expected in [(['-l',str(PHP)],'No syntax errors'),
                              ([str(PHP),'selftest'],'MPW_MAIN_ONLY_BRIDGE_SELFTEST=PASS')]:
            p=subprocess.run([php,*args],capture_output=True,text=True,timeout=25)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            self.assertIn(expected,p.stdout)
if __name__=='__main__':unittest.main()
