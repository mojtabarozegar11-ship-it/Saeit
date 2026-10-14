"""Mock-only preview of Farm Toolkit in the *installed* MojPlayWin branded store.

The installed branded view is core.brand_views.branded_store, not store_home.
Only the product query is mocked. No Product.save/update, SQL write,
product approval, payment intent, or publication happens.

Run by a maintainer with the live project's Python interpreter and
DJANGO_SETTINGS_MODULE=config.settings before running the free publisher.
"""
from __future__ import annotations

from copy import copy
from decimal import Decimal
from html.parser import HTMLParser
import json
from pathlib import Path
from unittest.mock import patch

EXPECTED_TITLE = "Farm Enterprise Economics Toolkit"
EXPECTED_HREF = "/factory-releases/farm-enterprise-economics-v1/"
EXPECTED_ZIP = EXPECTED_HREF + "Farm_Enterprise_Economics_Toolkit_Free_v1.zip"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs=[]
    def handle_starttag(self, tag, attrs):
        if tag=="a":
            self.hrefs.extend([v for k,v in attrs if k=="href" and isinstance(v,str)])


def preview_farm_in_branded_store():
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection
    from django.test import RequestFactory
    from core import brand_views
    from core.models import Product, Order, PaymentIntent
    from core.brand import brand_for_request

    if settings.DEBUG is not False or connection.vendor!="mysql":
        raise RuntimeError("EXPECTED_LIVE_DJANGO_READ_ONLY_CONTEXT")
    request=RequestFactory().get("/store/",HTTP_HOST="mojplaywin.com")
    brand=brand_for_request(request)
    if not brand or brand.code!="mojplaywin":
        raise RuntimeError("UNEXPECTED_BRANDED_STORE_TARGET")
    farm=Product.objects.get(pk=131)
    water=Product.objects.get(pk=147)
    if (farm.active or farm.price != Decimal("0.00")
        or farm.currency!="USD"
        or farm.metadata.get("factory_recipe")!="farm_enterprise_economics"
        or water.active or water.price!=Decimal("0.99")):
        raise RuntimeError("UNEXPECTED_PRODUCT_STATE_ABORT_PREVIEW")

    active_before=list(Product.objects.filter(active=True).order_by("-id"))
    orders_before=Order.objects.count()
    payments_before=PaymentIntent.objects.count()
    preview=copy(farm)
    preview.active=True
    preview.title="Farm Enterprise Economics Toolkit — Free Edition"
    preview.metadata=dict(farm.metadata, **{
        "factory_status":"published_free",
        "factory_publication_permission":True,
        "factory_public_url":EXPECTED_HREF+"index.html",
        "factory_public_download_url":EXPECTED_ZIP,
        "factory_commercial_status":"published_free_download_no_checkout",
    })

    class PreviewQuerySet(list):
        def order_by(self, *args):
            return self

    original_manager=brand_views.Product.objects
    if original_manager.model is not Product:
        raise RuntimeError("LIVE_VIEW_PRODUCT_MANAGER_UNEXPECTED")

    # No database update: substitute only the result of the existing active
    # catalog query inside the view. All other product attributes are read
    # from the original persisted factory record.
    with patch.object(original_manager,"filter",return_value=PreviewQuerySet(
        [preview]+[p for p in active_before if p.pk!=preview.pk]
    )) as filter_mock:
        response=brand_views.branded_store(request)
        if not filter_mock.called:
            raise RuntimeError("BRANDED_STORE_NOT_READING_ACTIVE_CATALOG")
        if filter_mock.call_args.kwargs != {"active": True}:
            raise RuntimeError("BRANDED_STORE_CHANGED_QUERY_SEMANTICS")

    if response.status_code!=200:
        raise RuntimeError("BRANDED_STORE_PREVIEW_RENDER_ERROR")

    html=response.content.decode("utf8","replace")
    parser=Links()
    parser.feed(html)
    visible=EXPECTED_TITLE in html
    linked=any(href in (EXPECTED_HREF,EXPECTED_ZIP,EXPECTED_HREF+"index.html") for href in parser.hrefs)
    db_unchanged=(
        not Product.objects.get(pk=131).active
        and not Product.objects.get(pk=147).active
        and Order.objects.count()==orders_before
        and PaymentIntent.objects.count()==payments_before
    )
    if not db_unchanged:
        raise RuntimeError("PRODUCTION_STATE_CHANGED_DURING_MOCK_PREVIEW")
    result={
        "existing_store_template_shows_synthetic_approved_farm":visible,
        "existing_store_template_contains_free_download_link":linked,
        "preview_does_not_write_product_or_payment_records":db_unchanged,
        "original_live_active_count":len(active_before),
        "production_activation_performed":False,
    }
    print(json.dumps(result,sort_keys=True))
    if not visible or not linked:
        raise RuntimeError("NATIVE_STORE_NEEDS_ADDITIVE_FREE_LINK_BEFORE_ACTIVATION")
    return result


if __name__=="__main__":
    preview_farm_in_branded_store()
