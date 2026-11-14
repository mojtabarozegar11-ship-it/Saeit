"""Isolated Django tests of the existing single-bot owner-only artifact inspector.

No real DB, SMTP, customer, VPS, token, payment or on-chain access.
"""
import hashlib
from io import StringIO
import json
from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.economic_master_agent import EconomicMasterAgent
from core.models import Product
from core.private_asset_byte_evidence import SCHEMA


class PrivateAssetOwnerGateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser(
            username="asset-evidence-owner", password="synthetic-only",
            email="owner@agri-market.org",
        )
        self.ref = "asset_1234567890123456"
        self.payload = b"%PDF-1.7\nprivate synthetic seed, not a buyer file\n%%EOF\n"
        self.root_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.root_dir.cleanup)
        self.root = Path(self.root_dir.name) / "restricted"
        self.root.mkdir()
        self.root.chmod(0o700)
        sha = hashlib.sha256(self.payload).hexdigest()
        manifest = {
            "schema": SCHEMA,
            "asset_ref": self.ref,
            "format": "pdf",
            "version": "1.0.0",
            "asset_sha256": sha,
            "asset_size": len(self.payload),
        }
        self.bin_file = self.root / (self.ref + ".pdf")
        self.bin_file.write_bytes(self.payload)
        self.bin_file.chmod(0o600)
        self.manifest = self.root / (self.ref + ".manifest.json")
        blob = json.dumps(manifest, sort_keys=True).encode()
        self.manifest.write_bytes(blob)
        self.manifest.chmod(0o600)
        self.product = Product.objects.create(
            title="Private test reference PDF", product_type="digital",
            active=True, price="20.00", currency="USD", owner=self.owner,
            metadata={
                "delivery_format": "pdf",
                "delivery_version": "1.0.0",
                "delivery_asset_ref": self.ref,
                "delivery_asset_sha256": sha,
                "delivery_manifest_sha256": hashlib.sha256(blob).hexdigest(),
                "rights_cleared": True,
                "independent_qc_reviewed": True,
                "buyer_terms_approved": True,
            },
        )
        self.bot = EconomicMasterAgent()

    def audit(self):
        with override_settings(
            MPW_PRIVATE_ASSET_AUDIT_APPROVED=True,
            MPW_PRIVATE_DELIVERY_ROOT=str(self.root),
        ):
            return self.bot.inspect_private_delivery_bytes_readonly(self.product.pk)

    def test_01_owner_gate_is_default_disabled(self):
        with override_settings(MPW_PRIVATE_ASSET_AUDIT_APPROVED=False):
            self.assertEqual(
                self.bot.inspect_private_delivery_bytes_readonly(self.product.pk)["reason"],
                "OWNER_APPROVAL_REQUIRED",
            )

    def test_02_approval_string_is_not_true(self):
        with override_settings(MPW_PRIVATE_ASSET_AUDIT_APPROVED="true"):
            self.assertEqual(
                self.bot.inspect_private_delivery_bytes_readonly(self.product.pk)["reason"],
                "OWNER_APPROVAL_REQUIRED",
            )

    def test_03_active_private_file_matches_but_not_a_sale(self):
        out = self.audit()
        self.assertTrue(out["private_file_bytes_verified"])
        self.assertFalse(out["delivery_allowed"])
        self.assertFalse(out["independent_settlement_verified"])

    def test_04_missing_private_root_blocks(self):
        with override_settings(MPW_PRIVATE_ASSET_AUDIT_APPROVED=True,
                               MPW_PRIVATE_DELIVERY_ROOT=None):
            out = self.bot.inspect_private_delivery_bytes_readonly(self.product.pk)
        self.assertEqual(out["reason"], "ROOT_NOT_CONFIGURED")

    def test_05_inactive_product_is_not_verified(self):
        self.product.active = False
        self.product.save(update_fields=["active"])
        self.assertEqual(self.audit()["reason"], "PRODUCT_NOT_ACTIVE_OR_MISSING")

    def test_06_deleted_product_is_not_verified(self):
        self.assertEqual(
            self.bot.inspect_private_delivery_bytes_readonly(-1)["reason"],
            "OWNER_APPROVAL_REQUIRED",
        )
        with override_settings(MPW_PRIVATE_ASSET_AUDIT_APPROVED=True):
            out = self.bot.inspect_private_delivery_bytes_readonly(2147483647)
        self.assertEqual(out["reason"], "PRODUCT_NOT_ACTIVE_OR_MISSING")

    def test_07_boolean_product_id_invalid(self):
        with override_settings(MPW_PRIVATE_ASSET_AUDIT_APPROVED=True):
            out = self.bot.inspect_private_delivery_bytes_readonly(True)
        self.assertEqual(out["reason"], "PRODUCT_IDENTIFIER_INVALID")

    def test_08_zero_product_id_invalid(self):
        with override_settings(MPW_PRIVATE_ASSET_AUDIT_APPROVED=True):
            out = self.bot.inspect_private_delivery_bytes_readonly(0)
        self.assertEqual(out["reason"], "PRODUCT_IDENTIFIER_INVALID")

    def test_09_owner_inactive_denied(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.assertEqual(self.audit()["reason"], "PRODUCT_OWNER_UNAUTHORIZED")

    def test_10_owner_not_staff_denied(self):
        self.owner.is_staff = False
        self.owner.save(update_fields=["is_staff"])
        self.assertEqual(self.audit()["reason"], "PRODUCT_OWNER_UNAUTHORIZED")

    def test_11_owner_not_superuser_denied(self):
        self.owner.is_superuser = False
        self.owner.save(update_fields=["is_superuser"])
        self.assertEqual(self.audit()["reason"], "PRODUCT_OWNER_UNAUTHORIZED")

    def test_12_modified_file_does_not_match_manifest(self):
        self.bin_file.write_bytes(self.payload + b"tampered")
        self.assertEqual(self.audit()["reason"], "ASSET_SHA256_MISMATCH")

    def test_13_source_metadata_rights_not_approved(self):
        meta = dict(self.product.metadata)
        meta["rights_cleared"] = False
        self.product.metadata = meta
        self.product.save(update_fields=["metadata"])
        self.assertEqual(self.audit()["reason"], "PRODUCT_APPROVAL_INCOMPLETE")

    def test_14_license_format_does_not_read_pdf(self):
        meta = dict(self.product.metadata)
        meta["delivery_format"] = "license_key"
        self.product.metadata = meta
        self.product.save(update_fields=["metadata"])
        self.assertEqual(self.audit()["reason"], "NOT_A_PRIVATE_FILE_FORMAT")

    def test_15_single_bot_management_command_returns_redacted_json(self):
        with override_settings(
            MPW_PRIVATE_ASSET_AUDIT_APPROVED=True,
            MPW_PRIVATE_DELIVERY_ROOT=str(self.root),
        ):
            buf = StringIO()
            call_command("mojtaba_private_asset_readonly",
                         product_id=self.product.pk, stdout=buf)
        out = json.loads(buf.getvalue())
        self.assertEqual(out["bot_id"], "mojtaba.bot.ai")
        self.assertTrue(out["private_file_bytes_verified"])
        self.assertNotIn(str(self.root), buf.getvalue())
        self.assertNotIn(self.ref, buf.getvalue())
        self.assertNotIn("agri-market.org", buf.getvalue())

    def test_16_command_invalid_product_id_rejected_without_io(self):
        with self.assertRaises(CommandError):
            call_command("mojtaba_private_asset_readonly", product_id=0)

    def test_17_no_order_or_payment_created_by_file_inspection(self):
        from core.models import Order, PaymentIntent, LedgerEntry, OrderItem
        before = (Product.objects.count(), Order.objects.count(),
                  OrderItem.objects.count(), PaymentIntent.objects.count(),
                  LedgerEntry.objects.count())
        self.assertTrue(self.audit()["private_file_bytes_verified"])
        after = (Product.objects.count(), Order.objects.count(),
                 OrderItem.objects.count(), PaymentIntent.objects.count(),
                 LedgerEntry.objects.count())
        self.assertEqual(before, after)

    def test_18_command_without_explicit_approval_does_not_read_file(self):
        with override_settings(MPW_PRIVATE_ASSET_AUDIT_APPROVED=False):
            buf = StringIO()
            call_command("mojtaba_private_asset_readonly",
                         product_id=self.product.pk, stdout=buf)
        out = json.loads(buf.getvalue())
        self.assertEqual(out["reason"], "OWNER_APPROVAL_REQUIRED")
        self.assertFalse(out["private_file_bytes_verified"])

    def test_19_missing_real_asset_is_not_verified(self):
        self.bin_file.unlink()
        self.assertEqual(self.audit()["reason"], "PRIVATE_FILE_UNAVAILABLE")

    def test_20_file_evidence_keeps_delivery_and_settlement_separate(self):
        out = self.audit()
        self.assertTrue(out["private_file_bytes_verified"])
        self.assertFalse(out["delivery_allowed"])
        self.assertFalse(out["buyer_email_verified"])
        self.assertFalse(out["customer_download_receipt_verified"])
        self.assertFalse(out["rights_independently_verified"])
