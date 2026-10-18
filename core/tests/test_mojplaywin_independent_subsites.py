"""Preview routing may never capture any independent path under MojPlayWin.

This compares candidate URL resolution to the existing SHARED Django URLConf;
it is a source-only regression. Live cPanel/Passenger independent child-site
routing still requires separate inventory, backups and actual smoke tests.
"""
from django.test import SimpleTestCase
from django.urls import Resolver404, resolve

PROTECTED_PATH_EXAMPLES = (
    "/mojtaba.roozegar/",
    "/mojtaba.roozegar/about/",
    "/picm/",
    "/picm/login/",
    "/studio.Roham/",
    "/saman/",
    "/zahra$$/",
    "/farnaz/",
    "/farnaz/admin/",
    "/taniya/",
    "/not-yet-inventoried-independent-project/",
)


def match_signature(path, urlconf):
    try:
        match = resolve(path, urlconf=urlconf)
    except Resolver404:
        return ("unregistered_in_shared_source",)
    func = match.func
    return (
        "registered",
        getattr(func, "__module__", ""),
        getattr(func, "__qualname__", repr(func)),
        match.url_name,
        tuple(sorted(match.kwargs.items())),
    )


class MojPlayWinIndependentSubsitesTests(SimpleTestCase):
    def test_main_site_preview_does_not_capture_any_protected_route(self):
        for path in PROTECTED_PATH_EXAMPLES:
            with self.subTest(path=path):
                baseline = match_signature(path, "config.urls")
                preview = match_signature(path, "core.mojplaywin_atelier_preview_urls")
                self.assertEqual(
                    baseline,
                    preview,
                    f"New MojPlayWin design illegally changed another subsite route: {path}",
                )

    def test_only_the_main_site_may_receive_new_brand_routes(self):
        for path in ("/web-engineering/", "/ai/", "/blockchain/", "/support/"):
            with self.subTest(path=path):
                preview = match_signature(path, "core.mojplaywin_atelier_preview_urls")
                self.assertEqual(preview[0], "registered")
        for path in PROTECTED_PATH_EXAMPLES:
            with self.subTest(path=path):
                preview = match_signature(path, "core.mojplaywin_atelier_preview_urls")
                self.assertNotIn("core.mojplaywin_web_views", str(preview))
                self.assertNotIn("core.mojplaywin_views", str(preview))
