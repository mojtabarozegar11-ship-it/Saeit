"""Offline HTTP guard tests for the independently gated paid-download view.

No real wallets, checkout operations, or production documents are involved.
"""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings

from mpw_commerce.downloads import download_paid_item


class PrivateDownloadHttpTests(SimpleTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"books").mkdir()
        self.asset=self.root/"books"/"example.pdf"
        self.asset.write_bytes(b"%PDF-1.4\nTest fixture only\n")
        self.request_factory=RequestFactory()
        self.authenticated=SimpleNamespace(is_authenticated=True,pk=101)
        self.item=SimpleNamespace(
            product=SimpleNamespace(metadata={"mpw_commerce":{
                "private_file":"books/example.pdf"
            }}),
        )
        self.settings=override_settings(
            MPW_COMMERCE_DOWNLOADS_ENABLED=True,
            MPW_COMMERCE_PRIVATE_ASSET_ROOT=str(self.root),
            ALLOWED_HOSTS=["mojplaywin.com","zomorodmelal.ir","testserver"],
        )
        self.settings.enable()
        self.addCleanup(self.settings.disable)

    def request(self,*,secure=True,host="mojplaywin.com"):
        r=self.request_factory.get(
            "/commerce/download/1/",secure=secure,HTTP_HOST=host,
        )
        r.user=self.authenticated
        return r

    def test_unreleased_private_download_never_looks_up_payment(self):
        with override_settings(MPW_COMMERCE_DOWNLOADS_ENABLED=False), patch(
            "mpw_commerce.downloads.can_access_purchased_digital_item"
        ) as access:
            with self.assertRaises(Http404):
                download_paid_item(self.request(),1)
            access.assert_not_called()

    def test_plain_http_and_other_domains_are_rejected(self):
        with patch("mpw_commerce.downloads.can_access_purchased_digital_item") as access:
            self.assertEqual(
                download_paid_item(self.request(secure=False),1).status_code,403
            )
            self.assertEqual(
                download_paid_item(self.request(host="zomorodmelal.ir"),1).status_code,
                403,
            )
            access.assert_not_called()

    def test_unpaid_or_different_customer_must_not_receive_content(self):
        with patch(
            "mpw_commerce.downloads.can_access_purchased_digital_item",
            return_value=False,
        ) as access:
            with self.assertRaises(Http404):
                download_paid_item(self.request(),1)
            access.assert_called_once_with(1,101)

    def test_eligible_buyer_receives_private_attachment_not_filesystem_path(self):
        with patch(
            "mpw_commerce.downloads.can_access_purchased_digital_item",
            return_value=True,
        ),patch(
            "mpw_commerce.downloads.OrderItem.objects.select_related"
        ) as queryset:
            queryset.return_value.filter.return_value.first.return_value=self.item
            response=download_paid_item(self.request(),1)
        self.assertEqual(response.status_code,200)
        self.assertIn("attachment",response["Content-Disposition"])
        self.assertIn("no-store",response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"],"nosniff")
        self.assertEqual(b"".join(response.streaming_content),self.asset.read_bytes())
        response.close()

    def test_disallowed_private_asset_path_rejected_even_if_buyer_has_entitlement(self):
        self.item.product.metadata["mpw_commerce"]["private_file"]="../bad.pdf"
        with patch(
            "mpw_commerce.downloads.can_access_purchased_digital_item",
            return_value=True,
        ),patch(
            "mpw_commerce.downloads.OrderItem.objects.select_related"
        ) as queryset:
            queryset.return_value.filter.return_value.first.return_value=self.item
            with self.assertRaises(Http404):
                download_paid_item(self.request(),1)
