from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase


class MojPlayWinSurfaceContractTests(SimpleTestCase):
    def test_home_and_products_use_shared_catalog(self):
        root = Path(settings.BASE_DIR) / 'core' / 'templates' / 'brands' / 'mojplaywin'
        for name in ('home.html', 'page.html'):
            source = (root / name).read_text(encoding='utf-8')
            self.assertIn('data-mpw-catalog', source)
            self.assertIn('/api/mojplaywin/catalog/', source)

    def test_base_loads_separate_assets(self):
        path = Path(settings.BASE_DIR) / 'core' / 'templates' / 'brands' / 'mojplaywin' / 'base.html'
        source = path.read_text(encoding='utf-8')
        for name in ('mojplaywin-navigation.css', 'mojplaywin-surfaces.css', 'mojplaywin-catalog.js'):
            self.assertIn(name, source)

    def test_public_catalog_scopes_brand(self):
        path = Path(settings.BASE_DIR) / 'core' / 'mojplaywin_catalog_engine.py'
        source = path.read_text(encoding='utf-8')
        self.assertIn('metadata__brand_code="mojplaywin"', source)
        self.assertIn('knowledge_article__published=True', source)
