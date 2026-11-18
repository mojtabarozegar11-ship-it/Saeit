"""Static contract checks for isolated prelaunch URL wiring.

These checks are NOT Django runtime integration tests; a real Django app
with authorized MojPlayWin routing is still required before any release.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
URLS = ROOT / "config/urls.py"
VIEW = ROOT / "core/mojprop_v141_info_view.py"
PAGE = ROOT / "templates/moj-prop-plan1-v141-prelaunch/index.html"


class V141InfoRouteSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.urls = URLS.read_text("utf-8")
        cls.view = VIEW.read_text("utf-8")
        cls.html = PAGE.read_text("utf-8")

    def test_01_url_compiles_without_importing_django(self):
        ast.parse(self.urls)

    def test_02_view_compiles_without_importing_django(self):
        ast.parse(self.view)

    def test_03_template_exists_in_dedicated_review_path(self):
        self.assertTrue(PAGE.is_file())
        self.assertIn("moj-prop-plan1-v141-prelaunch/index.html", self.view)

    def test_04_exact_new_root_url(self):
        self.assertIn('path("moj-prop-v141-info/", moj_prop_v141_public_info, name="moj_prop_v141_info")', self.urls)

    def test_05_new_route_precedes_old_generic_language_route(self):
        self.assertLess(self.urls.index('path("moj-prop-v141-info/"'),
                        self.urls.index('path("moj-prop/<str:lang>/"'))

    def test_06_existing_owner_urls_remain_unchanged(self):
        for old in ('path("moj-prop/"', 'path("moj-prop-interest/"',
                    'path("moj-prop-interest/form/"'):
            self.assertIn(old, self.urls)

    def test_07_old_plan1_reserved_path_not_claimed(self):
        self.assertNotIn('path("moj-prop/plan1/"', self.urls)
        self.assertNotIn('path("moj-prop/<str:lang>/plan1/"', self.urls)

    def test_08_domain_allowlist_two_mojplaywin_hosts_only(self):
        self.assertIn('"mojplaywin.com"',self.view)
        self.assertIn('"www.mojplaywin.com"',self.view)
        self.assertIn("host not in _ALLOWED_HOSTS", self.view)
        self.assertNotIn('"zomorodmelal.ir"',self.view)

    def test_09_https_mandatory(self):
        self.assertIn("request.is_secure() is not True",self.view)

    def test_10_non_get_head_returns_405(self):
        self.assertIn('request.method not in ("GET", "HEAD")', self.view)
        self.assertIn('HttpResponseNotAllowed(["GET", "HEAD"])',self.view)

    def test_11_query_data_rejected_instead_of_mirrored(self):
        self.assertIn('request.META.get("QUERY_STRING", "")',self.view)
        self.assertIn('raise Http404("Unexpected query data")',self.view)

    def test_12_strict_cache_no_store(self):
        self.assertIn('"private, no-store, max-age=0"',self.view)
        self.assertIn("@never_cache",self.view)

    def test_13_clickjacking_disallowed(self):
        self.assertIn('response["X-Frame-Options"] = "DENY"',self.view)
        self.assertIn("frame-ancestors 'none'",self.view)

    def test_14_payment_and_remote_network_disallowed(self):
        self.assertIn("form-action 'none'",self.view)
        self.assertIn("connect-src 'none'",self.view)
        self.assertIn("default-src 'none'",self.view)

    def test_15_search_indexing_prevented(self):
        self.assertIn('"noindex, nofollow, noarchive"',self.view)
        self.assertIn('noindex,nofollow,noarchive',self.html)

    def test_16_no_checkout_or_db_orm_imported_by_new_view(self):
        executable = ast.parse(self.view)
        imported = set()
        called = []
        for node in ast.walk(executable):
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module)
            elif isinstance(node, ast.Call):
                called.append(ast.unparse(node.func))
        self.assertNotIn("django.db", imported)
        self.assertNotIn("prop_firm.models", imported)
        for forbidden in ("objects.create", "objects.update", "objects.delete",
                          "send_email", "send_mail", "request.POST", "request.body"):
            self.assertNotIn(forbidden, called)

    def test_17_no_broker_adapter_or_executor_import(self):
        self.assertNotIn("broker", self.view.lower())
        self.assertNotIn("ctrader", self.view.lower())
        self.assertNotIn("metatrader", self.view.lower())

    def test_18_fixed_render_template(self):
        self.assertIn('"moj-prop-plan1-v141-prelaunch/index.html"', self.view)
        self.assertIn('"moj-prop-plan1-v141-prelaunch/info_20.html"', self.view)

    def test_19_no_untrusted_forwarded_host_lookup(self):
        self.assertIn('request.get_host()',self.view)
        self.assertNotIn('HTTP_X_FORWARDED_HOST',self.view)

    def test_20_exactly_two_optional_email_links_no_forms(self):
        self.assertEqual(self.html.count('href="mailto:mojplaywin@gmail.com'), 2)
        self.assertNotIn("<form",self.html)
        self.assertNotIn("<input",self.html)


if __name__ == "__main__":
    unittest.main()
