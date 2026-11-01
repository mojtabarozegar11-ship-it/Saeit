"""Regression for safe Zomorod office login until private Django ERP cutover.

Offline-only AST checks: never opens a database, establishes a session or
contacts production. The existing private PHP business app remains canonical
until a separately approved full release replaces the fallback.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
URLCONF = ROOT / "config/urls.py"
PHP_ENTRY = ROOT / "content/zomorod-business/index.php"
BUSINESS_HTACCESS = ROOT / "content/zomorod-business/.htaccess"


def route_call(route_name):
    tree = ast.parse(URLCONF.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "path" or not node.args:
            continue
        literal = node.args[0]
        if isinstance(literal, ast.Constant) and literal.value == route_name:
            return node
    raise AssertionError("Missing route " + route_name)


def redirect_settings(route_name):
    node = route_call(route_name)
    view = node.args[1]
    assert isinstance(view, ast.Call)
    assert isinstance(view.func, ast.Attribute) and view.func.attr == "as_view"
    assert isinstance(view.func.value, ast.Name) and view.func.value.id == "RedirectView"
    kwargs = {p.arg: p.value for p in view.keywords}
    assert isinstance(kwargs.get("url"), ast.Constant)
    assert isinstance(kwargs.get("permanent"), ast.Constant)
    return kwargs["url"].value, kwargs["permanent"].value


class ZomorodOfficeCanonicalFallbackTests(unittest.TestCase):
    def test_login_and_office_root_share_existing_business_entry(self):
        self.assertEqual(redirect_settings("company/office/login/"), ("/business/", False))
        self.assertEqual(redirect_settings("company/office/"), ("/business/", False))

    def test_login_stays_above_generic_company_routes(self):
        source = URLCONF.read_text(encoding="utf-8")
        self.assertLess(source.index('path("company/office/login/"'),
                        source.index('path("company/office/"'))
        self.assertLess(source.index('path("company/office/"'),
                        source.index('path("company/<slug:slug>/"'))

    def test_django_admin_is_not_used_as_company_login(self):
        source = URLCONF.read_text(encoding="utf-8")
        self.assertNotIn('url="/admin/login/?next=/staff/command-center/"', source)
        url, permanent = redirect_settings("company/office/login/")
        self.assertTrue(url.startswith("/") and not url.startswith("//"))
        self.assertFalse(permanent)

    def test_isolated_php_entry_exists_and_never_includes_a_public_db(self):
        entry = PHP_ENTRY.read_text(encoding="utf-8")
        self.assertIn("/.private/zomorod-business/app.php", entry)
        self.assertIn("is_file($entry)", entry)
        self.assertIn("http_response_code(503)", entry)
        self.assertNotIn("management.sqlite3", entry)

    def test_php_business_path_bypasses_root_passenger(self):
        conf = BUSINESS_HTACCESS.read_text(encoding="utf-8")
        self.assertIn("PassengerEnabled off", conf)
        self.assertIn("Options -Indexes", conf)
        self.assertIn("DirectoryIndex index.php", conf)


if __name__ == "__main__":
    unittest.main()
