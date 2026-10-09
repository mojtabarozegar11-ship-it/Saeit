from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase
from django.template.loader import get_template


class MojPlayWinNavigationTests(SimpleTestCase):
    def test_navigation_include_renders(self):
        html = get_template('brands/mojplaywin/includes/mega_nav.html').render({})
        for label in ('Products', 'Services', 'Markets', 'Knowledge', 'Innovation', 'Company', 'About Us'):
            self.assertIn(label, html)
        self.assertIn('href="/about/"', html)
        self.assertEqual(html.count('<details'), html.count('</details>'))

    def test_base_references_isolated_navigation(self):
        base = get_template('brands/mojplaywin/base.html')
        self.assertIsNotNone(base)
        path = Path(settings.BASE_DIR) / 'core' / 'templates' / 'brands' / 'mojplaywin' / 'base.html'
        source = path.read_text(encoding='utf-8')
        self.assertIn('includes/mega_nav.html', source)
        self.assertIn('mojplaywin-navigation.css', source)
        self.assertIn('mpw-brand', source)
