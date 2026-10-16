"""Conservative visible production note removal tests; no live host required."""
import importlib.util
import pathlib
import unittest

S=pathlib.Path(__file__).resolve().parents[1]/"scripts/mojtaba_remove_visible_production_notes.py"
spec=importlib.util.spec_from_file_location("clean_visible",S)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class CleanupTests(unittest.TestCase):
    def test_editorial_wrapper_removed_without_article_loss(self):
        page='<article id="MPW-001"><h3>Real research</h3><p>Research must use evidence.</p></article><p>'+m.BLOCKS[0]+'</p>'
        new,changes=m.clean_template(page)
        self.assertIn('id="MPW-001"',new)
        self.assertIn("Research must use evidence.",new)
        self.assertNotIn(m.BLOCKS[0],new)
        self.assertNotIn("<p></p>",new)
        self.assertTrue(changes)
    def test_photo_attribution_remains(self):
        text='<p>Photograph: Adrian Yu / Unsplash. Illustrative scene, not a verified business meeting.</p>'
        new,_=m.clean_template(text)
        self.assertIn("Photograph: Adrian Yu / Unsplash.",new)
        self.assertNotIn("not a verified business meeting",new)
    def test_images_and_links_preserved(self):
        text='<section id="mpw-primary-personal-profile-20261016"><img src="/original.webp" alt="Mojtaba Roozegar"/><a href="/mojtaba.roozegar/blog/">Journal</a><small>'+m.BLOCKS[1]+'</small></section>'
        new,_=m.clean_template(text)
        self.assertIn('src="/original.webp"',new)
        self.assertIn('href="/mojtaba.roozegar/blog/"',new)
        self.assertIn('id="mpw-primary-personal-profile-20261016"',new)
        self.assertNotIn(m.BLOCKS[1],new)
    def test_visible_ids_removed_only_from_labels(self):
        text='<span class="mpw-article-id">Research note · MPW-011</span><article id="MPW-011">Real text</article>'
        new,_=m.clean_template(text)
        self.assertIn('<article id="MPW-011">',new)
        self.assertIn('>Research note</span>',new)
        self.assertNotIn(">Research note · MPW-011</span>",new)
    def test_count_badge_removed_but_section_remains(self):
        text='<section id="mpw-fifty-editorials-20261015"><span class="mpw-overline">The personal editorial collection · 12 entries</span><h2>Research</h2></section>'
        new,_=m.clean_template(text)
        self.assertIn('id="mpw-fifty-editorials-20261015"',new)
        self.assertIn("<h2>Research</h2>",new)
        self.assertNotIn("12 entries",new)
    def test_research_warning_kept(self):
        text="A numerical example is hypothetical. Apply local agricultural and legal requirements."
        new,n=m.clean_post_content(text)
        self.assertEqual(new,text)
        self.assertEqual(n,0)
    def test_remove_only_blog_publication_sentence(self):
        src=m.ARTICLE_PRODUCTION_NOTES[0]+" Numerical scenarios are illustrative. Apply local professional and legal requirements before practical use."
        after,n=m.clean_post_content(src)
        self.assertEqual(n,1)
        self.assertNotIn("Editorial note:",after)
        self.assertIn("Numerical scenarios are illustrative",after)
    def test_idempotent(self):
        text='<p>'+m.BLOCKS[2]+'</p><h2>Original knowledge</h2>'
        a,_=m.clean_template(text);b,c=m.clean_template(a)
        self.assertEqual(a,b)
        self.assertEqual(c,{})
    def test_protected_root_and_minimums(self):
        self.assertEqual(m.MIN_POSTS,93)
        self.assertGreaterEqual(m.MIN_IMAGES,300)
        self.assertIn("mojtaba_roozegar_personal_v17",str(m.APP))
        self.assertNotIn("public_html",str(m.APP))
if __name__=="__main__":unittest.main()
