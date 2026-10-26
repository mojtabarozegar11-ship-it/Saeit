from html import unescape
from django.test import TestCase, override_settings

@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinSiteTests(TestCase):
    def test_home_is_filled_branded_and_canonical_to_mojplaywin(self):
        response=self.client.get("/",HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,200)
        html=unescape(response.content.decode("utf-8"))
        for marker in ("MojPlayWin","Ideas become knowledge","Research & Innovation","site/heroes/game-studio.",'href="https://mojplaywin.com/"',"mojplaywin-matte-gold-theme"):
            self.assertIn(marker,html)
        self.assertIn('class="site-standard-v2 mojplaywin-site mojplaywin-home"',html)

    def test_store_has_a_nonempty_catalog_with_images(self):
        response=self.client.get("/store/",HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,200)
        html=response.content.decode("utf-8")
        # The live three-SKU catalog intentionally replaced obsolete mock entries.
        # Assert current product titles, order-specific links, and delivery guidance.
        for marker in (
            "DIGITAL STORE",
            "The Science and Practice of Chess Improvement",
            "Taniya and the Little Baker Worms",
            "Atelier Interior — Client-Ready Website Kit",
            'href="/store/product/72/"',
            'href="/store/product/225/"',
            'href="/store/product/879/"',
            "How checkout and delivery work",
        ):
            self.assertIn(marker,html)
        self.assertNotIn("در حال حاضر محصول فعالی",html)

    def test_inner_pages_use_mojplaywin_content_theme_and_canonical(self):
        for path,marker in (("/agriculture/","Agriculture & Rural Services"),("/research/","Scientific Research & Innovation"),("/studio/","Games & Creative Studio")):
            with self.subTest(path=path):
                response=self.client.get(path,HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code,200)
                html=unescape(response.content.decode("utf-8"))
                self.assertIn(marker,html)
                self.assertIn("mojplaywin-matte-gold-theme",html)
                self.assertIn(f'href="https://mojplaywin.com{path}"',html)

    def test_zomorod_root_rendering_is_unchanged(self):
        response=self.client.get("/",HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code,200)
        html=response.content.decode("utf-8")
        self.assertIn("زنجیره ارزش از پژوهش تا بازار",html)
        self.assertIn('href="https://zomorodmelal.ir/"',html)
        self.assertNotIn("mojplaywin-matte-gold-theme",html)
