"""Founder belongs on real final copyright line INSIDE main footer."""
import re
import unittest
from scripts import mojplaywin_footer_true_lastline as m

def fixture(root):
    identity="MJWP_ROOT_CANDIDATE_ONLY_20261017" if root else "noindex,nofollow,noarchive"
    return ("""<html><head><title>MojPlayWin</title>
<style id="mpw-footer-refined-gold-v3">
.mw-site-footer .mpw-footer-bottom-signoff{grid-column:1/-1}
</style></head><body>"""+
      identity+'<main><article>'+'X'*5000+'</article></main>'+
      '<footer class="mw-site-footer" data-design="mojplaywin-atelier-v4">'+
      '<div><strong>MojPlayWin</strong><p>Play. Build. Evolve.</p></div>'+
      '<nav><a href="/store/">Store</a><a href="/research/">Research</a></nav>'+
      '<div class="mw-legal"><strong>Connect &amp; legal</strong></div>'+
      '<div class="mpw-footer-bottom-signoff" data-mpw-bottom-signoff="true"><span class="mpw-signoff-gold" data-emboss="Mojtaba Roozegar">Mojtaba Roozegar</span></div>'+
      '</footer><div class="mpx-bottom-bar"><span>© 2022 MojPlayWin. All rights reserved.</span><span>Built for research, creativity and responsible commerce.</span></div>'+
      '</body></html>').encode("utf-8")

class TrueFinalLineTests(unittest.TestCase):
    def test_move_real_copyright_into_footer_with_single_founder_at_end(self):
        for root in (True,False):
            with self.subTest(root=root):
                raw=fixture(root)
                after=m.rewrite(raw,root).decode()
                footer=re.search(r'<footer.*?</footer>',after,re.S).group()
                self.assertIn('class="mpx-bottom-bar"',footer)
                self.assertEqual(footer.count('data-mpw-copyright-founder="true"'),1)
                self.assertEqual(footer.count('<span>© 2022 MojPlayWin. All rights reserved.</span>'),1)
                self.assertEqual(footer.count('<span>Built for research, creativity and responsible commerce.</span>'),1)
                self.assertGreater(footer.index('Mojtaba Roozegar'),footer.index('© 2022 MojPlayWin'))
                self.assertTrue(footer.rstrip().endswith('</div>\n</footer>'))
                self.assertNotIn('</footer><div class="mpx-bottom-bar">',after)
                self.assertNotIn('data-mpw-bottom-signoff="true"',after)
                self.assertIn('X'*5000,after)
                self.assertIn('/store/',after)
                self.assertIn('grid-column:1/-1',after)
                with self.assertRaises(RuntimeError):m.rewrite(after.encode(),root)
    def test_changed_original_copyright_fails_closed(self):
        with self.assertRaises(RuntimeError):
            m.rewrite(fixture(True).replace(b'2022',b'2023'),True)

if __name__=="__main__":
    unittest.main()
