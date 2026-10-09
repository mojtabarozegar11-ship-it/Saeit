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

    def test_product_page_does_not_claim_live_checkout(self):
        path = Path(settings.BASE_DIR) / 'core' / 'templates' / 'brands' / 'mojplaywin' / 'product.html'
        source = path.read_text(encoding='utf-8')
        self.assertIn('Order availability.', source)
        self.assertNotIn('Secure order path.', source)

    def test_factory_products_require_release_gate_for_public_surfaces(self):
        base = Path(settings.BASE_DIR) / 'core'
        for filename in ('brand_views.py', 'mojplaywin_catalog_engine.py'):
            source = (base / filename).read_text(encoding='utf-8')
            self.assertIn('factory_release_gate__status="approved"', source)
            self.assertIn('factory_managed=False', source)

    def test_order_lock_is_inside_transaction_and_factory_release_checked(self):
        source = (Path(settings.BASE_DIR) / 'core' / 'api.py').read_text(encoding='utf-8')
        section = source.split('class OrderViewSet(', 1)[1].split('class PaymentIntentViewSet(', 1)[0]
        self.assertLess(section.index('with transaction.atomic():'), section.index('Product.objects.select_for_update()'))
        self.assertIn('factory_release_gate__status="approved"', section)

    def test_about_identifies_site_director_without_claiming_incorporation(self):
        source = (Path(settings.BASE_DIR) / 'core' / 'templates' / 'brands' / 'mojplaywin' / 'page.html').read_text(encoding='utf-8')
        self.assertIn('Mojtaba Roozegar', source)
        self.assertIn('Website Owner &amp; Director', source)
        self.assertIn("{% if page_key == 'about' %}", source)
        self.assertIn('does not imply a separately registered legal entity', source)

    def test_order_quantity_is_bounded(self):
        source = (Path(settings.BASE_DIR) / 'core' / 'api.py').read_text(encoding='utf-8')
        section = source.split('class OrderViewSet(', 1)[1].split('class PaymentIntentViewSet(', 1)[0]
        self.assertIn('1 <= quantity <= 100', section)
        self.assertIn('quantity must be between 1 and 100.', section)

    def test_payment_intent_and_owner_approval_share_transaction(self):
        source = (Path(settings.BASE_DIR) / 'core' / 'api.py').read_text(encoding='utf-8')
        section = source.split('class PaymentIntentViewSet(', 1)[1].split('class PaymentWebhookViewSet(', 1)[0]
        self.assertLess(section.index('with transaction.atomic():'), section.index('PaymentIntent.objects.create('))
        self.assertLess(section.index('PaymentIntent.objects.create('), section.index('ApprovalRequest.objects.create('))
        self.assertIn('Owner approval required before initiating an external payment.', section)
