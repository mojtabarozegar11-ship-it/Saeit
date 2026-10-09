from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase
from django.template.loader import get_template


class MojPlayWinTemplateIntegrationTests(SimpleTestCase):
    def test_products_page_has_live_catalog(self):
        template = get_template('brands/mojplaywin/page.html')
        page = {'title': 'Products', 'kicker': 'FACTORY', 'headline': 'Products', 'body': 'Digital products', 'cards': []}
        rendered = template.render({'page': page, 'page_key': 'products'})
        self.assertIn('data-mpw-catalog', rendered)
        self.assertIn('/api/mojplaywin/catalog/', rendered)

    def test_about_does_not_load_product_catalog(self):
        template = get_template('brands/mojplaywin/page.html')
        page = {'title': 'About Us', 'kicker': 'ABOUT', 'headline': 'About', 'body': 'Our mission', 'cards': []}
        rendered = template.render({'page': page, 'page_key': 'about'})
        self.assertNotIn('data-mpw-catalog', rendered)
        self.assertIn('OUR ECOSYSTEM', rendered)

    def test_assets_referenced_by_base_exist(self):
        root = Path(settings.BASE_DIR) / 'core' / 'static' / 'site'
        for filename in ('mojplaywin-surfaces.css', 'mojplaywin-catalog.js', 'mojplaywin-navigation.css'):
            self.assertTrue((root / filename).is_file())
