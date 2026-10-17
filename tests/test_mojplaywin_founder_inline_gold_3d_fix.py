"""Synthetic checks: the golden 3D founder belongs INSIDE the footer brand column,
not an external boxed grid tile. Never connect to production in unit tests.
"""
import unittest
from scripts.mojplaywin_founder_inline_gold_3d_fix import rewrite,NEW_STYLE,MARKER

def fixture(production):
    flavor = "root" if production else "preview"
    index = "MJWP_ROOT_CANDIDATE_ONLY_20261017" if production else 'noindex,nofollow,noarchive'
    return ("""<html><head><title>MojPlayWin</title>"""
        + '<style id="mpw-'+flavor+'-founder-style">.mpw-old{border:2px solid goldenrod}</style></head>'
        + "<body>" + index + '<section id="existing-pages-and-images">' + ("A"*4500) + '</section>'
        + '<footer class="mw-site-footer" data-design="mojplaywin-atelier-v4">'
        + '<div><strong>MojPlayWin</strong><p>Play. Build. Evolve.</p></div>'
        + '<nav>Already-existing business links</nav><div>Existing legal links</div>'
        + '<div class="mpw-'+flavor+'-founder" data-mpw-'+flavor
        + '-founder-20261018="true" aria-label="Founder: Mojtaba Roozegar">'
        + '<strong>Mojtaba Roozegar</strong></div></footer></body></html>').encode()

class Footer3DTests(unittest.TestCase):
    def check(self, prod):
        original=fixture(prod)
        transformed=rewrite(original,prod).decode()
        self.assertEqual(transformed.count(MARKER),1)
        self.assertEqual(transformed.count('Mojtaba Roozegar'),3)
        self.assertNotIn('class="mpw-root-founder"',transformed)
        self.assertNotIn('class="mpw-preview-founder"',transformed)
        self.assertNotIn('mpw-old{border:',transformed)
        self.assertIn('background:linear-gradient',transformed)
        self.assertIn('transform:translate(2px,3px)',transformed)
        footer=transformed.split('<footer',1)[1]
        brand=footer.split('</div>',1)[0]
        self.assertIn('class="mpw-footer-founder-inline"',brand)
        self.assertIn('class="mpw-gold-3d"',brand)
        self.assertIn('Play. Build. Evolve.',brand)
        self.assertIn('Already-existing business links',transformed)
        self.assertIn('Existing legal links',transformed)
        self.assertIn('existing-pages-and-images',transformed)
        self.assertIn('A'*4500,transformed)
        self.assertIn('border:0!important',NEW_STYLE)
        self.assertIn('background:none!important',NEW_STYLE)
        self.assertIn('box-shadow:none!important',NEW_STYLE)
        self.assertIn('::before',NEW_STYLE)
        return transformed

    def test_real_root_signature_is_inside_brand_footer_not_above_it(self):
        t=self.check(True)
        self.assertIn("MJWP_ROOT_CANDIDATE_ONLY_20261017",t)
        self.assertNotIn("noindex,nofollow,noarchive",t)

    def test_all_preview_pages_get_inside_footer_gold_3d_without_new_card(self):
        t=self.check(False)
        self.assertIn("noindex,nofollow,noarchive",t)

    def test_repeated_application_fails_closed(self):
        with self.assertRaises(RuntimeError):
            rewrite(rewrite(fixture(True),True),True)

if __name__=="__main__":
    unittest.main()
