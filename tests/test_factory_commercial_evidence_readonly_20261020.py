"""Non-fabricating commercial evidence gates over real ZIP bytes and private rails."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("commercial_evidence", ROOT / "scripts/factory_commercial_evidence_readonly_20261020.py")
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class CommercialEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.goods = self.root / "digital-products"
        self.goods.mkdir()
        self.name = "test_recipe"
        self.folder = self.goods / self.name
        self.folder.mkdir()
        self.archive = self.folder / (self.name + "-internal-qa.zip")
        with zipfile.ZipFile(self.archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(self.name + "/README.md", "# Proprietary work\n")
            z.writestr(self.name + "/LICENSE.txt", "All rights reserved. No independent proof.\n")
            z.writestr(self.name + "/test_core.py", "assert 1 == 1\n")
        self.sha = a.file_hash(self.archive)
        self.manifest = {
            "recipe": self.name, "qa_status": "passed",
            "commercial_status": "private_internal_qa_pass_not_published",
            "public_listing_enabled": False, "owner_publication_approval": False,
            "price": None, "files": ["README.md", "LICENSE.txt", "test_core.py"],
            "artifact_sha256": self.sha, "source_sha256": "a"*64}
        (self.folder / "manufacturing_manifest.json").write_text(json.dumps(self.manifest))

    def test_observed_files_not_a_license(self):
        item = a.examine_product(self.folder)
        self.assertEqual(item["members_integrity_checked"], 3)
        self.assertEqual(item["rights_document_filename_candidates"], 1)
        self.assertFalse(item["each_component_commercial_license_verified"])
        self.assertFalse(item["sale_allowed_by_this_audit"])
        self.assertFalse(a.audit_factory(self.root)["paid_items_activated"])

    def test_corrupt_hash_fails(self):
        self.archive.write_bytes(self.archive.read_bytes() + b"tamper")
        with self.assertRaisesRegex(ValueError, "ARCHIVE_SHA_MISMATCH"):
            a.examine_product(self.folder)

    def test_unsafe_member_fails_even_when_manifest_and_archive_hash_match(self):
        with zipfile.ZipFile(self.archive, "w") as z:
            z.writestr(self.name + "/../malware.js", "alert(1)")
        self.manifest["artifact_sha256"] = a.file_hash(self.archive)
        self.manifest["files"] = ["../malware.js"]
        (self.folder / "manufacturing_manifest.json").write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, "ARCHIVE_MEMBER_UNSAFE"):
            a.examine_product(self.folder)

    def test_no_fake_merchant_binding_with_private_routes(self):
        d = self.root / "merchant-rails"
        for site, host in (("mojplaywin", "mojplaywin.com"), ("zomorodmelal", "zomorodmelal.ir")):
            p = d / "routes" / site
            p.mkdir(parents=True)
            for n in range(1, 41):
                f = {"site_host": host, "family_id": "F%02d" % n,
                     "collect_customer_payment": False,
                     "automatic_paid_entitlement": False,
                     "public_buy_button_enabled": False,
                     "merchant_api_configuration_verified_on_live_site": False}
                (p / ("F%02d.json" % n)).write_text(json.dumps(f))
        (d / "dashboard.json").write_text(json.dumps({
            "site_count": 2, "private_site_family_offer_routes": 80,
            "bank_shahr_gateway_psp_verified": False,
            "mojplaywin_crypto_live_receipt_verification_verified_here": False}))
        result = a.audit_rails(self.root)
        self.assertEqual(result["private_routes_checked"], 80)
        self.assertEqual(result["provider_identity_or_api_unverified_routes"], 80)
        self.assertFalse(result["legal_seller_gateway_contract_verified_by_this_audit"])
        p = d / "routes" / "mojplaywin" / "F01.json"
        x = json.loads(p.read_text())
        x["collect_customer_payment"] = True
        p.write_text(json.dumps(x))
        with self.assertRaisesRegex(ValueError, "MERCHANT_ROUTE_INTEGRITY_FAILURE"):
            a.audit_rails(self.root)


if __name__ == "__main__":
    unittest.main()
