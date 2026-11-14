"""No-network, no-write synthetic private-asset byte evidence regressions."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "core/private_asset_byte_evidence.py"
SPEC = importlib.util.spec_from_file_location("private_asset_evidence_20261114", SOURCE)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class PrivateAssetByteEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "owner-only-private-assets"
        self.root.mkdir(mode=0o700)
        self.root.chmod(0o700)
        self.ref = "asset_1234567890123456"
        self.payload = b"%PDF-1.7\nsynthetic, offline, no buyer data\n%%EOF\n"
        self.meta = {
            "delivery_format": "pdf",
            "delivery_asset_ref": self.ref,
            "delivery_version": "1.0.0",
            "rights_cleared": True,
            "independent_qc_reviewed": True,
            "buyer_terms_approved": True,
        }
        self.write_asset(self.payload, "pdf")

    def asset_path(self, fmt=None):
        return self.root / (self.ref + "." + (fmt or self.meta["delivery_format"]))

    def manifest_path(self):
        return self.root / (self.ref + ".manifest.json")

    def write_asset(self, data, fmt):
        self.meta["delivery_format"] = fmt
        self.asset_path().write_bytes(data)
        self.asset_path().chmod(0o600)
        self.meta["delivery_asset_sha256"] = hashlib.sha256(data).hexdigest()
        self.manifest = {
            "schema": module.SCHEMA, "asset_ref": self.ref, "format": fmt,
            "version": "1.0.0", "asset_sha256": self.meta["delivery_asset_sha256"],
            "asset_size": len(data),
        }
        self.write_manifest()

    def write_manifest(self, *, raw=None):
        if raw is None:
            raw = json.dumps(self.manifest, sort_keys=True).encode("utf-8")
        self.manifest_path().write_bytes(raw)
        self.manifest_path().chmod(0o600)
        self.meta["delivery_manifest_sha256"] = hashlib.sha256(raw).hexdigest()

    def run_probe(self, *, root=None):
        return module.verify_private_asset_readonly(
            self.meta, private_root=self.root if root is None else root,
        )

    def blocked(self, code, *, root=None):
        out = self.run_probe(root=root)
        self.assertEqual(out["state"], "blocked", out)
        self.assertEqual(out["reason"], code, out)
        self.assertFalse(out["private_file_bytes_verified"])
        self.assertFalse(out["delivery_allowed"])
        self.assertFalse(out["independent_settlement_verified"])

    def test_01_pdf_private_bytes_match(self):
        out = self.run_probe()
        self.assertEqual(out["state"], "local_bytes_matched_private_manifest_only")
        self.assertTrue(out["private_file_bytes_verified"])
        self.assertTrue(out["private_manifest_bytes_verified"])
        self.assertFalse(out["delivery_allowed"])
        self.assertFalse(out["customer_download_receipt_verified"])

    def test_02_epub_bytes_match(self):
        self.write_asset(b"PK\x03\x04synthetic-epub-bytes", "epub")
        self.assertTrue(self.run_probe()["private_file_bytes_verified"])

    def test_03_zip_bytes_match(self):
        self.write_asset(b"PK\x03\x04synthetic-zip-bytes", "zip")
        self.assertTrue(self.run_probe()["private_file_bytes_verified"])

    def test_04_absolute_pathlib_root_accepted(self):
        self.assertTrue(self.run_probe(root=Path(self.root))["private_file_bytes_verified"])

    def test_05_none_root_unconfigured(self):
        self.assertEqual(
            module.verify_private_asset_readonly(self.meta)["reason"],
            "ROOT_NOT_CONFIGURED",
        )

    def test_06_relative_root_denied(self):
        self.blocked("ROOT_UNSAFE", root="relative-folder")

    def test_07_root_filesystem_root_denied(self):
        self.blocked("ROOT_UNSAFE", root="/")

    def test_08_root_leaf_symlink_denied(self):
        link = self.root.parent / "syn-link"
        link.symlink_to(self.root, target_is_directory=True)
        self.blocked("ROOT_UNSAFE", root=link)

    def test_09_root_parent_symlink_denied(self):
        parent = self.root.parent / "link-parent"
        parent.symlink_to(self.root.parent, target_is_directory=True)
        self.blocked("ROOT_UNSAFE", root=parent / self.root.name)

    def test_10_root_group_read_denied(self):
        self.root.chmod(0o750)
        self.blocked("ROOT_PERMISSIONS_UNSAFE")

    def test_11_missing_asset_is_not_ready(self):
        self.asset_path().unlink()
        self.blocked("PRIVATE_FILE_UNAVAILABLE")

    def test_12_missing_manifest_is_not_ready(self):
        self.manifest_path().unlink()
        self.blocked("PRIVATE_FILE_UNAVAILABLE")

    def test_13_asset_symlink_denied(self):
        target = self.root.parent / "outside-buyer"
        target.write_bytes(self.payload)
        self.asset_path().unlink()
        self.asset_path().symlink_to(target)
        self.blocked("PRIVATE_FILE_UNAVAILABLE")

    def test_14_manifest_symlink_denied(self):
        target = self.root.parent / "outside-manifest"
        target.write_bytes(self.manifest_path().read_bytes())
        self.manifest_path().unlink()
        self.manifest_path().symlink_to(target)
        self.blocked("PRIVATE_FILE_UNAVAILABLE")

    def test_15_hardlinked_asset_denied(self):
        os.link(self.asset_path(), self.root / "alias")
        self.blocked("PRIVATE_FILE_PERMISSIONS_UNSAFE")

    def test_16_world_readable_asset_denied(self):
        self.asset_path().chmod(0o644)
        self.blocked("PRIVATE_FILE_PERMISSIONS_UNSAFE")

    def test_17_group_readable_manifest_denied(self):
        self.manifest_path().chmod(0o640)
        self.blocked("PRIVATE_FILE_PERMISSIONS_UNSAFE")

    def test_18_empty_asset_denied(self):
        self.write_asset(b"", "pdf")
        self.blocked("PRIVATE_FILE_SIZE_INVALID")

    def test_19_asset_above_bounded_cap_denied(self):
        with patch.object(module, "MAX_ASSET_BYTES", 8):
            self.blocked("PRIVATE_FILE_SIZE_INVALID")

    def test_20_asset_hash_mismatch_denied(self):
        self.asset_path().write_bytes(self.payload + b"tamper")
        self.blocked("ASSET_SHA256_MISMATCH")

    def test_21_manifest_hash_mismatch_denied(self):
        self.manifest_path().write_bytes(self.manifest_path().read_bytes() + b" ")
        self.blocked("MANIFEST_SHA256_MISMATCH")

    def test_22_manifest_duplicate_fields_denied(self):
        self.write_manifest(raw=b'{"schema":"a","schema":"b"}')
        self.blocked("MANIFEST_DUPLICATE_FIELDS")

    def test_23_manifest_bad_json_denied(self):
        self.write_manifest(raw=b"{not JSON}")
        self.blocked("MANIFEST_INVALID_JSON")

    def test_24_manifest_extra_field_denied(self):
        self.manifest["buyer_email"] = "must-never-be-in-manifest"
        self.write_manifest()
        self.blocked("MANIFEST_SCHEMA_INVALID")

    def test_25_manifest_wrong_schema_denied(self):
        self.manifest["schema"] = "unsupported.v2"
        self.write_manifest()
        self.blocked("MANIFEST_SCHEMA_INVALID")

    def test_26_manifest_other_asset_ref_denied(self):
        self.manifest["asset_ref"] = "asset_other_private_reference"
        self.write_manifest()
        self.blocked("MANIFEST_SOURCE_MISMATCH")

    def test_27_manifest_other_format_denied(self):
        self.manifest["format"] = "zip"
        self.write_manifest()
        self.blocked("MANIFEST_SOURCE_MISMATCH")

    def test_28_manifest_other_version_denied(self):
        self.manifest["version"] = "2.0.0"
        self.write_manifest()
        self.blocked("MANIFEST_SOURCE_MISMATCH")

    def test_29_manifest_other_asset_digest_denied(self):
        self.manifest["asset_sha256"] = "c" * 64
        self.write_manifest()
        self.blocked("MANIFEST_SOURCE_MISMATCH")

    def test_30_manifest_size_mismatch_denied(self):
        self.manifest["asset_size"] = 99999
        self.write_manifest()
        self.blocked("MANIFEST_SIZE_MISMATCH")

    def test_31_manifest_boolean_size_denied(self):
        self.manifest["asset_size"] = True
        self.write_manifest()
        self.blocked("MANIFEST_SIZE_MISMATCH")

    def test_32_pdf_magic_header_required(self):
        self.write_asset(b"not really a PDF", "pdf")
        self.blocked("ASSET_SIGNATURE_INVALID")

    def test_33_epub_zip_header_required(self):
        self.write_asset(b"improper archive", "epub")
        self.blocked("ASSET_SIGNATURE_INVALID")

    def test_34_traversal_asset_reference_denied(self):
        self.meta["delivery_asset_ref"] = "../private/external"
        self.blocked("ASSET_REF_INVALID")

    def test_35_array_asset_reference_denied(self):
        self.meta["delivery_asset_ref"] = ["asset_1234567890123456"]
        self.blocked("ASSET_REF_INVALID")

    def test_36_rights_false_denied(self):
        self.meta["rights_cleared"] = False
        self.blocked("PRODUCT_APPROVAL_INCOMPLETE")

    def test_37_qc_false_denied(self):
        self.meta["independent_qc_reviewed"] = False
        self.blocked("PRODUCT_APPROVAL_INCOMPLETE")

    def test_38_buyer_terms_false_denied(self):
        self.meta["buyer_terms_approved"] = False
        self.blocked("PRODUCT_APPROVAL_INCOMPLETE")

    def test_39_license_key_does_not_read_file(self):
        self.meta["delivery_format"] = "license_key"
        self.blocked("NOT_A_PRIVATE_FILE_FORMAT")

    def test_40_cosmetic_does_not_read_file(self):
        self.meta["delivery_format"] = "in_game_cosmetic"
        self.blocked("NOT_A_PRIVATE_FILE_FORMAT")

    def test_41_zero_digest_denied(self):
        self.meta["delivery_asset_sha256"] = "0" * 64
        self.blocked("ASSET_DIGEST_INVALID")

    def test_42_manifest_digest_equals_asset_digest_denied(self):
        self.meta["delivery_manifest_sha256"] = self.meta["delivery_asset_sha256"]
        self.blocked("ASSET_MANIFEST_DIGEST_IDENTICAL")

    def test_43_manifest_too_large_denied(self):
        self.write_manifest(raw=b"{" + b" " * (module.MAX_MANIFEST_BYTES + 1) + b"}")
        self.blocked("PRIVATE_FILE_SIZE_INVALID")

    def test_44_manifest_invalid_utf8_denied(self):
        self.write_manifest(raw=b"\xff\xfe")
        self.blocked("MANIFEST_INVALID_JSON")

    def test_45_manifest_nonfinite_denied(self):
        self.manifest["asset_size"] = float("nan")
        self.write_manifest()
        self.blocked("MANIFEST_NONFINITE")

    def test_46_output_redacts_paths_and_bytes(self):
        result = repr(self.run_probe())
        self.assertNotIn(str(self.root), result)
        self.assertNotIn(self.ref, result)
        self.assertNotIn("synthetic", result)
        self.assertNotIn("buyer@", result)

    def test_47_readonly_does_not_change_files(self):
        files = (self.asset_path(), self.manifest_path())
        before = [(f.read_bytes(), f.stat().st_mtime_ns) for f in files]
        self.assertTrue(self.run_probe()["read_only"])
        after = [(f.read_bytes(), f.stat().st_mtime_ns) for f in files]
        self.assertEqual(before, after)

    def test_48_bad_version_type_denied(self):
        self.meta["delivery_version"] = ["1.0.0"]
        self.blocked("VERSION_INVALID")

    def test_49_bogus_manifest_root_object_denied(self):
        self.write_manifest(raw=b"[]")
        self.blocked("MANIFEST_SCHEMA_INVALID")

    def test_50_no_false_customer_or_cash_attestation(self):
        out = self.run_probe()
        for name in ("rights_independently_verified", "buyer_email_verified",
                     "independent_settlement_verified", "delivery_allowed",
                     "customer_download_receipt_verified"):
            self.assertIs(out[name], False)
