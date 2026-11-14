"""Conversion sitemap guard for six verified catalogue-backed service scope pages."""
from xml.etree import ElementTree

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from core.service_sales_controls import SERVICE_CARDS


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_company_sitemap_contains_all_six_service_scope_paths_exactly_once():
    response = Client().get(reverse("sitemap_xml"))
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/xml")
    document = ElementTree.fromstring(response.content)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locations = [
        el.text for el in document.findall("s:url/s:loc", ns)
    ]
    for service_code in SERVICE_CARDS:
        official_url = (
            "https://zomorodmelal.ir"
            + reverse("service_scope_page", args=[service_code])
        )
        assert locations.count(official_url) == 1
    assert all(u.startswith("https://zomorodmelal.ir/") for u in locations)
    assert not any("https://mojplaywin.com" in u for u in locations)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_all_sitemap_service_pages_resolve_to_an_actual_buyer_offer():
    client = Client()
    for code, card in SERVICE_CARDS.items():
        res = client.get(reverse("service_scope_page", args=[code]))
        assert res.status_code == 200
        assert card["title_fa"] in res.content.decode("utf-8")
