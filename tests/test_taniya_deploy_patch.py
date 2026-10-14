from pathlib import Path

import pytest

from scripts.taniya_patch import patch_urls, patch_views


def test_taniya_patch_is_idempotent_for_main_source():
    urls = Path("config/urls.py").read_text(encoding="utf-8")
    views = Path("core/views.py").read_text(encoding="utf-8")

    assert patch_urls(urls) == urls
    assert patch_views(views) == views


def test_taniya_patch_adds_route_and_view_to_base_source():
    urls = Path("config/urls.py").read_text(encoding="utf-8")
    views = Path("core/views.py").read_text(encoding="utf-8")

    base_urls = urls.replace(
        "from core.views import home, platform_page, taniya_studio",
        "from core.views import home, platform_page",
    ).replace('    path("taniya/", taniya_studio, name="taniya_studio"),\\n', "")
    base_views = views.replace(
        "@never_cache\\ndef taniya_studio(request):\\n"
        '    return render(request, "taniya_studio/index.html")\\n\\n\\n',
        "",
    ).replace(
        '"links":[{"title":"Taniya Studio","text":"20 playful browser games","url":"/taniya/"},',
        '"links":[',
    )

    patched_urls = patch_urls(base_urls)
    patched_views = patch_views(base_views)
    assert 'path("taniya/", taniya_studio, name="taniya_studio")' in patched_urls
    assert 'def taniya_studio(request):' in patched_views
    assert '"title":"Taniya Studio"' in patched_views


def test_taniya_patch_fails_closed_for_unrecognized_source():
    with pytest.raises(ValueError):
        patch_urls("urlpatterns = []")
    with pytest.raises(ValueError):
        patch_views("def unrelated_view(request): pass")
