"""MojPlayWin home-theme unification boundaries; do not import product/payment logic."""
import unittest
from pathlib import Path

from core.templatetags.mpw_shell import shell_mode

ROOT = Path(__file__).resolve().parents[1]


class MainSiteThemeBoundaryTests(unittest.TestCase):
    def test_main_template_pages_avoid_duplicate_navigation(self):
        for path in ("/", "/store/", "/company/", "/research/", "/knowledge/",
                     "/market/", "/economy/", "/studio/", "/agents/", "/industry/",
                     "/services/", "/ventures/jewelry-gold/", "/ventures/crypto/"):
            with self.subTest(path=path):
                self.assertEqual(shell_mode("mojplaywin.com", path), "managed")

    def test_interior_pages_receive_home_theme(self):
        for path in ("/search/", "/agriculture/", "/agriculture/livestock/",
                     "/amozeshgah/", "/amozeshgah/course/existing/",
                     "/academy/", "/education/", "/knowledge/article/example/",
                     "/blog/", "/blog/hello/", "/newsletter/", "/newsletter/a/",
                     "/weather/", "/auctions/", "/company-gallery/",
                     "/company-content/example/"):
            with self.subTest(path=path):
                self.assertEqual(shell_mode("www.mojplaywin.com", path), "legacy")

    def test_sibling_sites_admin_api_and_checkout_are_never_themed(self):
        for path in ("/farnaz/", "/farnaz/admin/", "/zahra/", "/roham/",
                     "/saman/", "/taniya/", "/mojtaba.roozegar/", "/picm/",
                     "/tala/", "/mohammad/", "/ghanadi/", "/staff/",
                     "/staff/command-center/", "/admin/", "/api/products/",
                     "/api/payments/", "/api/payment-webhooks/", "/checkout/",
                     "/payment/complete/", "/cart/", "/orders/", "/login/",
                     "/unknown-feature/", "//weird/", "/favicon.ico"):
            with self.subTest(path=path):
                self.assertEqual(shell_mode("mojplaywin.com", path), "skip")

    def test_other_domains_are_never_modified(self):
        for host in ("zomorodmelal.ir", "www.zomorodmelal.ir",
                     "mojplaywin.com.attacker.invalid", "example.org"):
            for path in ("/", "/blog/", "/store/", "/newsletter/"):
                self.assertEqual(shell_mode(host, path), "skip")
        self.assertEqual(shell_mode("mojplaywin.com:443", "/search/"), "legacy")

    def test_shell_is_additive_to_preexisting_content(self):
        page = (ROOT / "core/templates/base.html").read_text(encoding="utf-8")
        self.assertIn("{% block content %}{% endblock %}", page)
        self.assertIn("{% mpw_shell_mode request as mpw_mode %}", page)
        self.assertIn("{% if mpw_mode == 'legacy' %}", page)
        self.assertIn("{% include 'mojplaywin/theme.html' %}", page)
        self.assertIn("{% include 'mojplaywin/footer.html' %}", page)
        self.assertIn("zomorod-olive-site", page)
        self.assertIn("site-footer", page)

    def test_protected_product_template_keeps_original_links(self):
        brand = (ROOT / "core/templates/brands/mojplaywin/base.html").read_text(encoding="utf-8")
        for path in ("/store/", "/products/", "/crypto-payments/", "/commerce/"):
            self.assertIn('href="' + path + '"', brand)
        self.assertNotIn("mpw-unified-legacy", brand)
        self.assertNotIn("mojplaywin-inner-unified", brand)
        self.assertIn("{% block content %}{% endblock %}", brand)

    def test_home_and_store_keep_embedded_theme(self):
        for file in ("home.html", "store.html", "section.html"):
            body = (ROOT / "core/templates/mojplaywin" / file).read_text(encoding="utf-8")
            self.assertIn('{% include "mojplaywin/theme.html" %}', body)
            self.assertIn('{% include "mojplaywin/footer.html" %}', body)
            self.assertIn("{% block content %}", body)

    def test_actual_django_template_compilation_and_host_isolation(self):
        # Real Django template rendering (not only textual CSS/file checks).
        from django.conf import settings
        from django.template import Context, Engine
        if not settings.configured:
            settings.configure(STATIC_URL="/static/", INSTALLED_APPS=[])
        import django
        django.setup()
        engine = Engine(
            dirs=[str(ROOT / "core/templates")],
            libraries={"mpw_shell": "core.templatetags.mpw_shell", "static": "django.templatetags.static"},
        )
        base = engine.get_template("base.html")

        class Request:
            def __init__(self, host, path):
                self.host = host
                self.path = path

            def get_host(self):
                return self.host

        class User:
            is_authenticated = False

        def render(host, path):
            return base.render(Context({"request": Request(host, path), "user": User()}))

        internal = render("mojplaywin.com", "/search/")
        self.assertIn("mpw-unified-main", internal)
        self.assertIn('class="mw-site-nav"', internal)
        self.assertIn('class="mw-site-footer"', internal)
        self.assertIn("mojplaywin-inner-unified", internal)

        already_branded = render("mojplaywin.com", "/store/")
        self.assertNotIn("mpw-unified-main", already_branded)
        self.assertNotIn('class="mw-site-nav"', already_branded)

        for host, path in (("zomorodmelal.ir", "/search/"),
                           ("mojplaywin.com", "/farnaz/"),
                           ("mojplaywin.com", "/api/payments/")):
            with self.subTest(host=host, path=path):
                rendered = render(host, path)
                self.assertNotIn('class="mw-site-nav"', rendered)
                self.assertNotIn("mpw-unified-main", rendered)


    def test_no_payment_selector_or_checkout_override_in_unified_css(self):
        css = (ROOT / "core/static/site/mojplaywin-inner-unified.css").read_text(encoding="utf-8")
        self.assertNotIn("body.mpw-unified-legacy", css)
        self.assertIn("body.mojplaywin-site.mpw-unified-main", css)
        self.assertNotIn(".checkout-form", css)
        self.assertNotIn(".crypto-payment", css)
        self.assertNotIn(".payment-intent", css)


if __name__ == "__main__":
    unittest.main()
