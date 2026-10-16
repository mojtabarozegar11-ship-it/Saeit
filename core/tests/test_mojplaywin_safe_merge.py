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


def test_brand_home_route_dispatch_is_scoped_and_idempotent():
    live = (
        "from core.brand_views import branded_home, branded_page\\n"
        "from core.mojplaywin_views import venture\\n"
        "urlpatterns = [\\n"
        '    path("", branded_home, name="home"),\\n'
        '    path("store/", branded_page, name="store"),\\n'
        "]\\n"
    )

    merged = DEPLOY.route_mojplaywin_brand_home(live)

    assert 'path("", branded_home_dispatch, name="home")' in merged
    assert 'path("", branded_home, name="home")' not in merged
    assert 'path("store/", branded_page, name="store")' in merged
    assert "from core.mojplaywin_views import branded_home_dispatch" in merged
    assert DEPLOY.route_mojplaywin_brand_home(merged) == merged
