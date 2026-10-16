import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "deploy_mojplaywin_branding.py"
SPEC = importlib.util.spec_from_file_location("deploy_mojplaywin_branding", SCRIPT)
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


def test_insertion_keeps_live_host_lines_between_context():
    base = "from core.views import home\nurlpatterns = []\n"
    desired = "from core.views import home\nfrom core.mojplaywin_views import home\nurlpatterns = []\n"
    live = "from core.views import home\n# existing host-specific route\nurlpatterns = []\n"

    merged = DEPLOY.apply_three_way(base, desired, live, "config/urls.py")

    assert "from core.mojplaywin_views import home\n" in merged
    assert "# existing host-specific route\n" in merged
    assert merged.index("from core.mojplaywin_views import home") < merged.index("# existing host-specific route")


def test_conflicting_replacement_still_fails_closed():
    base = "def page():\n    return 'old'\n"
    desired = "def page():\n    return 'new'\n"
    live = "def page():\n    return 'local'\n"

    with pytest.raises(RuntimeError, match="Safe merge conflict"):
        DEPLOY.apply_three_way(base, desired, live, "core/views.py")


def test_brand_home_and_store_dispatch_are_scoped_and_idempotent():
    live = """from core.brand_views import branded_home, branded_store, branded_page
urlpatterns = [
    path("", branded_home, name="home"),
    path("store/", lambda request: branded_store(request) if brand_for_request(request) else store_home(request), name="store"),
    path("worlds/", branded_page, {"page": "worlds"}, name="mpw_worlds"),
]
"""

    merged = DEPLOY.route_mojplaywin_brand_home(live)
    merged = DEPLOY.route_mojplaywin_brand_store(merged)

    assert 'path("", branded_home_dispatch, name="home")' in merged
    assert 'path("", branded_home, name="home")' not in merged
    assert 'branded_store_dispatch(request) if brand_for_request(request)' in merged
    assert 'path("worlds/", branded_page, {"page": "worlds"}' in merged
    assert "from core.mojplaywin_views import branded_store_dispatch" in merged
    assert DEPLOY.route_mojplaywin_brand_store(merged) == merged
