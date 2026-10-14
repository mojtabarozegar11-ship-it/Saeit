import ast

import pytest

from scripts.taniya_patch import patch_urls, patch_views


BASE_URLS = """from django.urls import path
from core.views import platform_page

urlpatterns = [
    path("studio/", lambda request: platform_page(request, "studio"), name="studio"),
]
"""

BASE_VIEWS = """from django.shortcuts import render


def platform_page(request, section):
    return render(request, "core/platform.html")
"""


def test_patch_is_idempotent_for_main_source():
    urls = open("config/urls.py", encoding="utf-8").read()
    views = open("core/views.py", encoding="utf-8").read()

    assert patch_urls(urls) == urls
    assert patch_views(views) == views


def test_patch_adds_route_and_view_to_base_source():
    urls = patch_urls(BASE_URLS)
    views = patch_views(BASE_VIEWS)

    parsed_urls = ast.parse(urls)
    routes = [
        item for node in parsed_urls.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "urlpatterns" for target in node.targets)
        for item in node.value.elts
        if isinstance(item, ast.Call) and item.args and getattr(item.args[0], "value", None) == "taniya/"
    ]
    assert len(routes) == 1
    assert isinstance(routes[0].args[1], ast.Name)
    assert routes[0].args[1].id == "taniya_studio"
    assert "def taniya_studio(request):" in views
    assert 'render(request, "taniya_studio/index.html")' in views
    assert patch_urls(urls) == urls
    assert patch_views(views) == views


def test_patch_fails_closed_for_unrecognized_source():
    with pytest.raises(ValueError):
        patch_urls("urlpatterns = []")
    with pytest.raises(ValueError):
        patch_views("def unrelated_view(request): pass")
