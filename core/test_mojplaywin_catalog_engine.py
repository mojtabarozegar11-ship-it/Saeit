from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory
from django.urls import reverse
from core.mojplaywin_catalog_engine import public_catalog


class PublicCatalogEngineTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('core.mojplaywin_catalog_engine.brand_for_request', return_value=None)
    def test_other_brand_cannot_use_endpoint(self, _brand):
        from django.http import Http404
        with self.assertRaises(Http404):
            public_catalog(self.factory.get('/api/mojplaywin/catalog/'))

    @patch('core.mojplaywin_catalog_engine.brand_for_request', return_value=SimpleNamespace(code='mojplaywin'))
    def test_bad_limit_rejected_without_db_query(self, _brand):
        for value in ('abc', '0', '101'):
            response = public_catalog(self.factory.get('/api/mojplaywin/catalog/', {'limit': value}))
            self.assertEqual(response.status_code, 400)

    @patch('core.mojplaywin_catalog_engine.brand_for_request', return_value=SimpleNamespace(code='mojplaywin'))
    def test_catalog_rejects_mutating_methods(self, _brand):
        response = public_catalog(self.factory.post('/api/mojplaywin/catalog/'))
        self.assertEqual(response.status_code, 405)

    def test_url_is_registered(self):
        self.assertEqual(reverse('mojplaywin-public-catalog'), '/api/mojplaywin/catalog/')
