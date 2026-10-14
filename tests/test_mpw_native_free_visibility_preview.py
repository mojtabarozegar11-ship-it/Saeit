"""Mock-only regression tests for native MojPlayWin free activation preview."""
from html import escape
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import patch
from django.http import HttpResponse
from django.test import TestCase,override_settings
from django.db import connection
from core.models import Product
from scripts.mpw_native_free_visibility_preview import (
    EXPECTED_TITLE, EXPECTED_HREF, Links,preview_farm_in_branded_store,
)


class NativeFreePreviewTests(TestCase):
    def setUp(self):
        Product.objects.create(id=131,title=EXPECTED_TITLE,active=False,
            product_type="digital",price="0.00",currency="USD",
            metadata={"factory_recipe":"farm_enterprise_economics"})
        Product.objects.create(id=147,title="Water Budget Economics",active=False,
            product_type="digital",price="0.99",currency="USD",
            metadata={"factory_recipe":"water_budget_economics"})

    def preview(self,with_link=True,with_title=True):
        import core
        brand_module=ModuleType("core.brand")
        brand_module.brand_for_request=lambda req: SimpleNamespace(code="mojplaywin")
        view_module=ModuleType("core.brand_views")
        view_module.Product=Product
        def view(req):
            items=list(Product.objects.filter(active=True).order_by("-id"))
            assert len(items)==1
            title=escape(items[0].title) if with_title else "Empty catalog"
            link=f'<a href="{EXPECTED_HREF}">Free download</a>' if with_link else ""
            return HttpResponse(f"<html><main><h3>{title}</h3>{link}</main></html>")
        view_module.branded_store=view
        with (patch.dict(sys.modules,{"core.brand":brand_module,"core.brand_views":view_module}),
              patch.object(core,"brand_views",view_module,create=True),
              patch.object(connection,"vendor","mysql"),
              override_settings(DEBUG=False,ALLOWED_HOSTS=["mojplaywin.com"])):
            return preview_farm_in_branded_store()

    def test_mock_shows_existing_template_would_display_free_listing(self):
        result=self.preview()
        self.assertTrue(result["existing_store_template_shows_synthetic_approved_farm"])
        self.assertTrue(result["existing_store_template_contains_free_download_link"])
        self.assertFalse(result["production_activation_performed"])
        self.assertFalse(Product.objects.get(pk=131).active)
        self.assertFalse(Product.objects.get(pk=147).active)

    def test_free_product_missing_link_blocks_publication(self):
        with self.assertRaisesRegex(RuntimeError,"NATIVE_STORE_NEEDS_ADDITIVE_FREE_LINK"):
            self.preview(with_link=False)
        self.assertFalse(Product.objects.get(pk=131).active)

    def test_free_product_missing_title_blocks_publication(self):
        with self.assertRaisesRegex(RuntimeError,"NATIVE_STORE_NEEDS_ADDITIVE_FREE_LINK"):
            self.preview(with_title=False)
        self.assertFalse(Product.objects.get(pk=131).active)

    def test_parse_links_only_actual_anchors(self):
        scan=Links()
        scan.feed('<a href="/factory-releases/farm-enterprise-economics-v1/">Free</a><p href="/hack">Bad</p>')
        self.assertEqual(scan.hrefs,[EXPECTED_HREF])
