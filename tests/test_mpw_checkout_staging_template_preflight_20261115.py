"""Cutover fails early if staging has no actual email-bound checkout template."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from scripts import mpw_dynamic_store_cutover_20261108 as cutover


class StagingCheckoutPreflightTests(TestCase):
    def test_missing_real_checkout_template_blocks_before_django_or_site_changes(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"core").mkdir()
            (root/"services").mkdir()
            (root/"core/mojplaywin_views.py").write_text("def store(request): pass\n")
            (root/"services/mpw_trx_guest_commerce.py").write_text("guest=true\n")
            (root/"services/mpw_trx_email_recovery.py").write_text("email_required=true\n")
            with patch.object(cutover,"APP",root):
                with self.assertRaisesRegex(
                    RuntimeError,"STAGING_BUYER_EMAIL_TEMPLATE_MISSING"
                ):
                    cutover.check_actual_staging_store()

    def test_live_cutover_keeps_owner_approval_guard_after_new_template(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            with patch.object(cutover,"PUBLIC",root):
                with self.assertRaisesRegex(
                    RuntimeError,"OWNER_BUYER_EMAIL_REQUIRED_STORE_CUTOVER_DENIED"
                ):
                    cutover.require_owner_email_policy_before_cutover(root)

    def test_actual_template_source_contains_only_one_invoice_form(self):
        root=Path(__file__).resolve().parents[1]
        html=(root/"core/templates/mpw_commerce/product_checkout.html").read_text("utf-8")
        self.assertEqual(html.count("<form "),1)
        self.assertEqual(html.count("{% csrf_token %}"),1)
        self.assertIn('name="email" type="email"',html)
        self.assertNotIn("<script",html.lower())
