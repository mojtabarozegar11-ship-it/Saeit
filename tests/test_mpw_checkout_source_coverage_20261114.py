"""Read-only real repo + synthetic source completeness gates, no Django/payment."""
import ast
import json
import tempfile
import unittest
from pathlib import Path
from scripts import mpw_checkout_source_coverage_20261114 as m


SETTINGS = (
    'INSTALLED_APPS = ["django.contrib.auth", "mpw_commerce"]\n'
    'MIDDLEWARE = ["django.middleware.security.SecurityMiddleware",\n'
    '  "core.mpw_checkout_security_middleware.MojPlayWinCheckoutSecurityMiddleware"]\n'
)
ROUTES = (
    'from django.urls import path\n'
    'urlpatterns=[path("store/", lambda request: None),\n'
    '  path("store/product/<int:product_id>/checkout/", lambda request: None),\n'
    '  path("commerce/book/<int:product_id>/", lambda request: None),\n'
    '  path("commerce/trx-easy/start/<int:product_id>/", lambda request: None)]\n'
)


class BuyerSourceCoverageTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)

    def fixture(self):
        for name in m.REQUIRED:
            target=self.root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("source file for synthetic fixture\n")
        (self.root/"config/settings.py").write_text(SETTINGS)
        (self.root/"config/urls.py").write_text(ROUTES)
        return self.root

    def test_01_synthetic_complete_source_flag(self):
        self.fixture()
        self.assertTrue(m.audit(self.root)["complete_versioned_buyer_checkout_source_candidate"])

    def test_02_complete_source_cannot_authorize_release(self):
        self.fixture()
        self.assertFalse(m.audit(self.root)["release_permitted"])

    def test_03_complete_source_cannot_claim_live_worker(self):
        self.fixture()
        self.assertFalse(m.audit(self.root)["effective_passenger_app_verified"])

    def test_04_complete_source_cannot_claim_live_store(self):
        self.fixture()
        self.assertFalse(m.audit(self.root)["live_dynamic_store_verified"])

    def test_05_complete_source_cannot_claim_live_checkout_csp(self):
        self.fixture()
        self.assertFalse(m.audit(self.root)["live_checkout_csp_verified"])

    def test_06_complete_source_cannot_claim_paid_delivery(self):
        self.fixture()
        self.assertFalse(m.audit(self.root)["paid_delivery_verified"])

    def test_07_complete_source_cannot_claim_payment(self):
        self.fixture()
        self.assertFalse(m.audit(self.root)["actual_payment_verified"])

    def test_08_revenue_unknown_not_zero(self):
        self.fixture()
        self.assertIsNone(m.audit(self.root)["actual_collected_revenue"])

    def test_09_canonical_bot_exact(self):
        self.fixture()
        self.assertEqual(m.audit(self.root)["canonical_bot"],"mojtaba.bot.ai")

    def test_10_repository_requirement_count_fixed(self):
        self.assertEqual(len(m.REQUIRED),11)

    def test_11_all_requirements_restricted_to_repo_relative(self):
        self.assertTrue(all(not x.startswith("/") and ".." not in x.split("/")
                            for x in m.REQUIRED))

    def test_12_all_paths_unique(self):
        self.assertEqual(len(set(m.REQUIRED)),len(m.REQUIRED))

    def test_13_missing_entire_commerce_package_refuses_source_readiness(self):
        self.fixture()
        for name in m.REQUIRED:
            if name.startswith("mpw_commerce/"):
                (self.root/name).unlink()
        a=m.audit(self.root)
        self.assertFalse(a["complete_versioned_buyer_checkout_source_candidate"])
        self.assertEqual(sum(v=="missing_or_unsafe" for v in a["files"].values()),3)

    def test_14_missing_buyer_orders_module_blocks_source_readiness(self):
        self.fixture()
        (self.root/"mpw_commerce/buyer_orders.py").unlink()
        self.assertFalse(m.audit(self.root)["complete_versioned_buyer_checkout_source_candidate"])

    def test_15_missing_checkout_view_module_blocks_source_readiness(self):
        self.fixture()
        (self.root/"mpw_commerce/product_checkout_page.py").unlink()
        self.assertFalse(m.audit(self.root)["complete_versioned_buyer_checkout_source_candidate"])

    def test_16_missing_checkout_template_blocks_source_readiness(self):
        self.fixture()
        (self.root/"mpw_commerce/templates/mpw_commerce/product_checkout.html").unlink()
        self.assertFalse(m.audit(self.root)["complete_versioned_buyer_checkout_source_candidate"])

    def test_17_missing_email_recovery_migration_blocks_source_readiness(self):
        self.fixture()
        (self.root/"core/migrations/0049_mpw_guest_email_recovery.py").unlink()
        self.assertFalse(m.audit(self.root)["complete_versioned_buyer_checkout_source_candidate"])

    def test_18_missing_guest_adapter_blocks_source_readiness(self):
        self.fixture()
        (self.root/"services/mpw_trx_guest_commerce.py").unlink()
        self.assertFalse(m.audit(self.root)["complete_versioned_buyer_checkout_source_candidate"])

    def test_19_missing_email_recovery_adapter_blocks_source_readiness(self):
        self.fixture()
        (self.root/"services/mpw_trx_email_recovery.py").unlink()
        self.assertFalse(m.audit(self.root)["complete_versioned_buyer_checkout_source_candidate"])

    def test_20_missing_store_template_blocks_source_readiness(self):
        self.fixture()
        (self.root/"core/templates/mojplaywin/store.html").unlink()
        self.assertFalse(m.audit(self.root)["complete_versioned_buyer_checkout_source_candidate"])

    def test_21_missing_core_view_blocks_source_readiness(self):
        self.fixture()
        (self.root/"core/mojplaywin_views.py").unlink()
        self.assertFalse(m.audit(self.root)["complete_versioned_buyer_checkout_source_candidate"])

    def test_22_missing_store_dispatch_blocks_source_readiness(self):
        self.fixture()
        (self.root/"core/commerce_views.py").unlink()
        self.assertFalse(m.audit(self.root)["complete_versioned_buyer_checkout_source_candidate"])

    def test_23_missing_settings_refuses_middleware_claim(self):
        self.fixture()
        (self.root/"config/settings.py").unlink()
        r=m.audit(self.root)
        self.assertFalse(r["exact_checkout_csp_middleware_installed_in_settings_source"])

    def test_24_missing_urls_refuses_checkout_route_claims(self):
        self.fixture()
        (self.root/"config/urls.py").unlink()
        self.assertEqual(m.audit(self.root)["explicit_source_routes_count"],0)

    def test_25_missing_checkout_product_path_is_visible(self):
        self.fixture()
        r=(self.root/"config/urls.py")
        r.write_text(ROUTES.replace('  path("store/product/<int:product_id>/checkout/", lambda request: None),\n',''))
        self.assertFalse(m.audit(self.root)["explicit_source_routes"]["store/product/<int:product_id>/checkout/"])

    def test_26_missing_book_checkout_alias_visible(self):
        self.fixture()
        p=self.root/"config/urls.py"
        p.write_text(ROUTES.replace('  path("commerce/book/<int:product_id>/", lambda request: None),\n',''))
        self.assertFalse(m.audit(self.root)["explicit_source_routes"]["commerce/book/<int:product_id>/"])

    def test_27_missing_invoice_start_path_visible(self):
        self.fixture()
        p=self.root/"config/urls.py"
        p.write_text(ROUTES.replace('  path("commerce/trx-easy/start/<int:product_id>/", lambda request: None)]', ']'))
        self.assertFalse(m.audit(self.root)["explicit_source_routes"]["commerce/trx-easy/start/<int:product_id>/"])

    def test_28_missing_store_route_visible(self):
        self.fixture()
        p=self.root/"config/urls.py"
        p.write_text(ROUTES.replace('urlpatterns=[path("store/", lambda request: None),','urlpatterns=['))
        self.assertFalse(m.audit(self.root)["explicit_source_routes"]["store/"])

    def test_29_middleware_marker_in_comment_is_not_installation(self):
        self.fixture()
        p=self.root/"config/settings.py"
        p.write_text('INSTALLED_APPS=["mpw_commerce"]\nMIDDLEWARE=[]\n# '+m.MIDDLEWARE_PATH)
        self.assertFalse(m.audit(self.root)["exact_checkout_csp_middleware_installed_in_settings_source"])

    def test_30_app_marker_in_comment_is_not_installation(self):
        self.fixture()
        p=self.root/"config/settings.py"
        p.write_text('INSTALLED_APPS=[]\nMIDDLEWARE=["'+m.MIDDLEWARE_PATH+'"]\n# mpw_commerce')
        self.assertFalse(m.audit(self.root)["commerce_app_installed_in_reviewed_settings_source"])

    def test_31_checkout_route_string_in_comment_not_declared(self):
        self.fixture()
        p=self.root/"config/urls.py"
        p.write_text('# path("commerce/book/<int:product_id>/", x)\nurlpatterns=[]')
        self.assertFalse(m.audit(self.root)["explicit_source_routes"]["commerce/book/<int:product_id>/"])

    def test_32_invalid_python_syntax_is_not_valid_route_proof(self):
        self.fixture()
        (self.root/"config/urls.py").write_text("urlpatterns = [def invalid")
        self.assertEqual(m.audit(self.root)["explicit_source_routes_count"],0)

    def test_33_invalid_utf8_is_not_valid_route_proof(self):
        self.fixture()
        (self.root/"config/urls.py").write_bytes(b"\xff")
        self.assertEqual(m.audit(self.root)["explicit_source_routes_count"],0)

    def test_34_symlinked_checkout_module_not_followed(self):
        self.fixture()
        p=self.root/"mpw_commerce/product_checkout_page.py"
        p.unlink()
        p.symlink_to(self.root/"services/mpw_trx_guest_commerce.py")
        self.assertEqual(m.audit(self.root)["files"]["mpw_commerce/product_checkout_page.py"],"missing_or_unsafe")

    def test_35_symlinked_checkout_template_parent_not_followed(self):
        self.fixture()
        target=self.root/"mpw_commerce/templates/mpw_commerce"
        other=self.root/"elsewhere"
        other.mkdir()
        for f in target.iterdir():f.unlink()
        target.rmdir()
        target.symlink_to(other,target_is_directory=True)
        self.assertEqual(m.audit(self.root)["files"]["mpw_commerce/templates/mpw_commerce/product_checkout.html"],"missing_or_unsafe")

    def test_36_symlinked_root_refused(self):
        self.fixture()
        alias=self.root.parent/"repo-alias-test"
        alias.symlink_to(self.root,target_is_directory=True)
        self.addCleanup(alias.unlink)
        self.assertEqual(m.audit(alias)["source_files_present"],0)

    def test_37_zero_length_checkout_file_refused(self):
        self.fixture()
        (self.root/"mpw_commerce/buyer_orders.py").write_bytes(b"")
        self.assertFalse(m.audit(self.root)["complete_versioned_buyer_checkout_source_candidate"])

    def test_38_over_size_checkout_file_refused(self):
        self.fixture()
        (self.root/"mpw_commerce/buyer_orders.py").write_bytes(b"A"*(m.MAX_BYTES+1))
        self.assertFalse(m.audit(self.root)["complete_versioned_buyer_checkout_source_candidate"])

    def test_39_unknown_relative_file_cannot_be_read(self):
        self.fixture()
        self.assertIsNone(m.safe_read(self.root,"../../.env"))

    def test_40_nonstandard_file_cannot_be_read(self):
        self.fixture()
        self.assertIsNone(m.safe_read(self.root,"secrets.json"))

    def test_41_never_emits_directory_paths_or_raw_contents(self):
        self.fixture()
        report=json.dumps(m.audit(self.root))
        self.assertNotIn(str(self.root),report)
        self.assertNotIn("source file for synthetic fixture",report)

    def test_42_readonly_reports_no_disk_writes(self):
        self.fixture()
        self.assertFalse(m.audit(self.root)["files_modified"])

    def test_43_readonly_reports_no_customer_access(self):
        self.fixture()
        self.assertFalse(m.audit(self.root)["customer_data_read"])

    def test_44_readonly_reports_no_network(self):
        self.fixture()
        self.assertFalse(m.audit(self.root)["network_access"])

    def test_45_versioned_source_gap_not_proof_of_live_cpanel_gap(self):
        a=m.audit(self.root)
        self.assertTrue(a["missing_components_are_not_proof_of_absence_on_cpanel"])

    def test_46_exact_source_checkout_routes_required_count_is_four(self):
        self.assertEqual(len(m.EXPLICIT_ROUTES),4)

    def test_47_repeated_literal_route_is_not_multiple_coverage(self):
        self.fixture()
        p=self.root/"config/urls.py"
        p.write_text(ROUTES + '\npath("store/", lambda request: None)\n')
        self.assertEqual(m.audit(self.root)["explicit_source_routes_count"],4)

    def test_48_existing_no_unrelated_app_implication(self):
        self.fixture()
        a=m.audit(self.root)
        self.assertNotIn("can_deploy",a)

    def test_49_no_test_buyer_or_money_data_in_report(self):
        self.fixture()
        a=json.dumps(m.audit(self.root))
        self.assertNotIn("private_email",a)
        self.assertNotIn("txid",a)

    def test_50_main_covered_source_uses_new_narrow_middleware(self):
        # The actual source tree is deliberately incomplete at the buyer
        # package/URL layer. CI should not report it as ready.
        r=m.audit(m.ROOT)
        self.assertTrue(r["exact_checkout_csp_middleware_installed_in_settings_source"])
        self.assertFalse(r["complete_versioned_buyer_checkout_source_candidate"])
        self.assertFalse(r["release_permitted"])
