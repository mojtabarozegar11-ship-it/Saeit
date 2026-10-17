"""New footer treatment: understated metallic text as a bottom strip inside footer."""
import unittest
from scripts import mojplaywin_footer_refined_gold_bottom as m

def fixture(production):
    flag="MJWP_ROOT_CANDIDATE_ONLY_20261017" if production else "noindex,nofollow,noarchive"
    oldstyle='<style id="mpw-footer-gold-3d-inline-v2">.unattractive-giant-3d{filter:blur(3px)}</style>'
    oldline='<p class="mpw-footer-founder-inline" data-mpw-inline-gold-3d="true" aria-label="Mojtaba Roozegar"><strong class="mpw-gold-3d" data-text="Mojtaba Roozegar">Mojtaba Roozegar</strong></p>'
    return ("<html><head><title>MojPlayWin</title>"+oldstyle+"</head><body>"+flag+
       '<main id="original-sections">'+"A"*5000+'</main><footer class="mw-site-footer" data-design="mojplaywin-atelier-v4">'
       '<div><strong>MojPlayWin</strong><p>Play. Build. Evolve.</p>'+oldline+'</div>'
       '<nav aria-label="discover"><a href="/research/">Research</a></nav>'
       '<nav aria-label="business"><a href="/store/">Store</a></nav>'
       '<div class="mw-legal">Contact &amp; legal</div></footer></body></html>').encode("utf-8")

class RefinedFooterTests(unittest.TestCase):
    def validate(self,isprod):
        source=fixture(isprod)
        out=m.rewrite(source,isprod).decode()
        footer=out.split('<footer class="mw-site-footer"',1)[1].split("</footer>",1)[0]
        self.assertEqual(out.count(m.MARKER),1)
        self.assertEqual(out.count(m.SIGNOFF),1)
        self.assertLess(footer.index('class="mw-legal"'),footer.index('data-mpw-bottom-signoff'))
        self.assertNotIn('mpw-footer-founder-inline',out)
        self.assertNotIn('mpw-gold-3d',out)
        self.assertNotIn('unattractive-giant-3d',out)
        self.assertIn("border-top:1px solid rgba(214,174,96,.22)",out)
        self.assertIn("grid-column:1/-1",out)
        self.assertIn("translate(.65px,1.25px)",out)
        self.assertIn("background:transparent!important",out)
        self.assertIn("A"*5000,out)
        self.assertIn('<a href="/store/">Store</a>',out)
        self.assertIn("Play. Build. Evolve.",out)
        with self.assertRaises(RuntimeError):
            m.rewrite(out.encode(),isprod)
        return out

    def test_actual_root_static_page_signature_at_bottom_of_footer(self):
        out=self.validate(True)
        self.assertNotIn("noindex,nofollow,noarchive",out)

    def test_preview_pages_keep_noindex_and_original_navigation(self):
        out=self.validate(False)
        self.assertIn("noindex,nofollow,noarchive",out)

    def test_unexpected_unrelated_footer_fails_closed(self):
        raw=fixture(True).replace(b'class="mw-site-footer"',b'class="unrelated-footer"')
        with self.assertRaises(RuntimeError):m.rewrite(raw,True)

    def test_no_new_card_box_or_heavy_3d_extrusion(self):
        style=m.NEW_STYLE
        self.assertNotIn("border:2px",style)
        self.assertNotIn("transform:translate(2px,3px)",style)
        self.assertNotIn("box-shadow:0 12px",style)
        self.assertIn("font-size:clamp(.94rem,1.3vw,1.14rem)",style)
        self.assertIn("forced-colors:active",style)

if __name__=="__main__":
    unittest.main()
