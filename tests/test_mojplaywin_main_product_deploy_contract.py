"""Pure route + deployment package safety: no server changes."""
import importlib.util
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "deploy_mojplaywin_branding.py"
FLOW = ROOT / ".github" / "workflows" / "mojplaywin-main-deploy.yml"
spec = importlib.util.spec_from_file_location("mojplaywin_deploy_contract", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

COMPANY_IMPORT = "from core.commerce_views import store_home, auctions_home"
STORE_ROUTE = '    path("store/", store_home, name="store"),'
OLD_IMPORT = "from core.product_seo_views import product_detail"
OLD_PRODUCT = '    path("store/product/<int:product_id>/", product_detail, name="store_product_detail"),'
NEW_IMPORT = "from core.mojplaywin_product_detail import brand_product_detail"
NEW_PRODUCT = '    path("store/product/<int:product_id>/", brand_product_detail, name="store_product_detail"),'


class MojPlayWinMainProductDeployTests(TestCase):
    def test_add_product_route_to_pinned_previous_baseline(self):
        old = COMPANY_IMPORT + "\nurlpatterns = [\n" + STORE_ROUTE + "\n]\n"
        result = module.route_mojplaywin_product_detail(old)
        self.assertIn(NEW_IMPORT, result)
        self.assertIn(NEW_PRODUCT.strip(), result)
        self.assertIn(STORE_ROUTE, result)

    def test_replace_old_route_without_changing_company_store(self):
        old = COMPANY_IMPORT + "\n" + OLD_IMPORT + "\nurlpatterns = [\n" + STORE_ROUTE + "\n" + OLD_PRODUCT + "\n]\n"
        result = module.route_mojplaywin_product_detail(old)
        self.assertIn(COMPANY_IMPORT, result)
        self.assertIn(STORE_ROUTE, result)
        self.assertNotIn(OLD_PRODUCT, result)
        self.assertIn(NEW_PRODUCT.strip(), result)

    def test_new_route_is_idempotent(self):
        current = NEW_IMPORT + "\nurlpatterns = [\n" + STORE_ROUTE + "\n" + NEW_PRODUCT + "\n]"
        self.assertEqual(module.route_mojplaywin_product_detail(current), current)

    def test_conflicting_route_fails_closed(self):
        source = COMPANY_IMPORT + "\nurlpatterns = [\n" + STORE_ROUTE + "\n    path('x', view, name='store_product_detail'),\n]"
        with self.assertRaises(RuntimeError):
            module.route_mojplaywin_product_detail(source)

    def test_unknown_config_fails_closed(self):
        with self.assertRaises(RuntimeError):
            module.route_mojplaywin_product_detail("urlpatterns = []")

    def test_owned_release_tracks_both_new_files(self):
        paths = {str(item) for item in module.OWNED_FILES}
        self.assertIn("core/mojplaywin_product_detail.py", paths)
        self.assertIn("core/templates/mojplaywin/product_detail.html", paths)

    def test_whitelisted_package_and_smoke_cover_all_three_items(self):
        txt = FLOW.read_text(encoding="utf-8")
        for path in ("core/mojplaywin_product_detail.py", "core/templates/mojplaywin/product_detail.html"):
            self.assertGreaterEqual(txt.count(path), 3)
        for ident in (72, 225, 879):
            self.assertIn(f"https://mojplaywin.com/store/product/{ident}/", txt)

    def test_legacy_rollback_is_schema_aware(self):
        src = MODULE.read_text(encoding="utf-8")
        self.assertIn('manifest.get("__schema_version__") == 2', src)
        self.assertIn('manifest = {"__schema_version__": 2}', src)
