"""Audit that six-main-only work cannot mutate any protected route."""
import importlib.util
import pathlib
import subprocess
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
FILE=ROOT/"scripts/mpw_six_mainonly_atomic_20261019.py"
class MainOnlySixAtomicSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location("mpw_six",FILE)
        cls.m=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)
    def test_selftest(self):
        out=subprocess.run([sys.executable,str(FILE),"selftest"],capture_output=True,text=True,timeout=20)
        self.assertEqual(out.returncode,0,out.stderr)
        self.assertIn("MPW_SIX_SOURCE_SELFTEST=PASS",out.stdout)
    def test_allowlist_and_no_shared_edits(self):
        m=self.m
        self.assertEqual(len(m.STATIC),19)
        self.assertEqual(len({n for n,h in m.STATIC}),19)
        self.assertEqual(len({m.page_route(n) for n,h in m.STATIC}),19)
        self.assertTrue(all(len(sha)==64 for n,sha in m.STATIC))
        self.assertEqual(len(m.HOME_SHA),64)
        self.assertEqual(m.RULES.count("RewriteRule"),2)
        self.assertIn("^/search/$",m.RULES)
        self.assertIn("^/topics/$",m.RULES)
        for banned in ("/farnaz/","/saman/","/picm/","/taniya/","/roham/","/zahra/"):
            self.assertNotIn(banned,m.RULES)
        source=FILE.read_text()
        self.assertNotIn("passenger_wsgi.py').touch",source)
        self.assertNotIn("systemctl restart",source)
    def test_home_340_links_preserve_destination(self):
        m=self.m
        unit='<a class="mpo-orbit-card mpo-topic-card" href="/research/"><strong>Research</strong><small>Discover science</small></a>'
        doc=('<html><head></head><body>'+('<ul class="mpo-orbit-track">'+unit*20+'</ul>')*17+'</body></html>').encode()
        changed,cards=m.improve_home(doc)
        self.assertEqual(len(cards),340)
        self.assertEqual(len(set(c["id"] for c in cards)),340)
        self.assertTrue(all(c["category"]=="/research/" for c in cards))
        self.assertIn(b'/topics/?id=0340',changed)
        self.assertIn(b'noindex,follow',m.php_topic().encode())
    def test_search_contains_known_saleable_content_without_payment(self):
        m=self.m
        entries=m.index_data([{"id":"0001","title":"Chess methods","summary":"Chess evaluation","category":"/store/"}])
        self.assertIn(b"Chess",entries)
        self.assertIn(b"Taniya",entries)
        self.assertNotIn(b"private_key",entries)
        self.assertIn("htmlspecialchars",m.php_search())
        self.assertIn("Search MojPlayWin",m.php_search())
    def test_surgical_legacy_brand_removal(self):
        m=self.m
        doc='<header class="site-header">OLD</header><header class="mw-site-nav">GOOD</header><footer class="mw-site-footer">Mojtaba Roozegar</footer><footer class="site-footer">OLD</footer>'
        result=m.strip_legacy(doc)
        self.assertNotIn('class="site-header"',result)
        self.assertNotIn('class="site-footer"',result)
        self.assertIn('class="mw-site-nav"',result)
        self.assertIn('class="mw-site-footer"',result)
if __name__=="__main__":unittest.main()
