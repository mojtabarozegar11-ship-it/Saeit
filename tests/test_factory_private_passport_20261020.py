"""End-to-end non-commercial factory private product-passport checks."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

maker = load("passport_factory_maker", "scripts/factory_product_maker.py")
policy = load("passport_policy", "scripts/factory_personal_owner_passport_policy_20261020.py")


class PrivatePassportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.recipes = base / "recipes"
        self.root = base / "factory-private"
        self.out = self.root / "digital-products"
        shutil.copytree(ROOT / "product_recipes" / "farm_enterprise_economics",
                        self.recipes / "farm_enterprise_economics")
        self.slug = "farm_enterprise_economics"

    def build(self):
        result = maker.manufacture(self.slug, self.recipes, self.out)
        folder = self.out / self.slug
        manifest = json.loads((folder / "manufacturing_manifest.json").read_text("utf8"))
        passport = folder / result["private_passport"]
        return result, folder, manifest, passport

    def test_real_maker_generates_private_source_sha_bound_sidecar(self):
        result, folder, meta, sidecar = self.build()
        self.assertTrue(sidecar.is_file())
        self.assertEqual(sidecar.stat().st_mode & 0o777, 0o600)
        self.assertIn(meta["artifact_sha256"], sidecar.name)
        self.assertEqual(meta["private_passport_sha256"], policy.sha256_file(sidecar))
        p = json.loads(sidecar.read_text("utf8"))
        self.assertEqual(p["product_id"], self.slug)
        self.assertEqual(p["source_sha256"], meta["source_sha256"])
        self.assertEqual(p["artifact_sha256"], meta["artifact_sha256"])
        self.assertEqual(p["declared_person"], "مجتبی روزگار")
        self.assertEqual(len(p["declared_roles"]), 7)
        self.assertEqual(p["economic_rights"][0]["party"], "مجتبی روزگار")
        self.assertEqual(p["economic_rights"][0]["percent"], 100)
        self.assertEqual(p["company_role"], "execution_technology_and_commercial_platform_only_not_rights_owner")
        self.assertEqual(p["schema"], "saeit.factory.private-product-passport.v4")
        self.assertEqual(p["verified_roles"], [])
        self.assertFalse(p["commercial_release_allowed"])
        self.assertFalse(p["public_store_role_display"])
        self.assertFalse(p["company_operational_permission"]["executed_agreement_verified"])
        with zipfile.ZipFile(str(folder / (self.slug + "-internal-qa.zip"))) as archive:
            self.assertFalse(any("passport" in name for name in archive.namelist()))

    def test_1398_founding_signature_claim_is_not_backdated_2026_master(self):
        result, folder, meta, _ = self.build()
        context_file = folder / policy.ensure_private_passport(folder, meta)["company_context_file"]
        self.assertTrue(context_file.is_file())
        self.assertEqual(context_file.stat().st_mode & 0o777, 0o600)
        ctx = json.loads(context_file.read_text("utf8"))
        self.assertEqual(ctx["company"]["national_id"], "14008746024")
        self.assertEqual(ctx["company"]["registration_number"], "3110")
        self.assertEqual(ctx["company"]["registration_date_jalali"], "1398/08/16")
        self.assertEqual(ctx["historical_founding_documents"]["signed_year_jalali"], "1398")
        self.assertEqual(ctx["historical_founding_documents"]["signature_status"],
                         "owner_attested_signed_not_independently_verified")
        self.assertFalse(ctx["historical_founding_documents"]["signature_image_required_for_internal_attestation"])
        self.assertEqual(ctx["modern_master_document"]["reconstruction_year_jalali"], "1405")
        self.assertFalse(ctx["modern_master_document"]["updated_wording_execution_verified"])
        self.assertTrue(ctx["commercial_roles"]["personal_rights_not_assigned_to_company"])
        self.assertFalse(ctx["official_registry_independently_verified"])
        self.assertFalse(ctx["commercial_release_allowed"])
        # The previous v4 passport is not amended or signed by this sidecar.
        self.assertEqual(meta["private_passport_schema"], "saeit.factory.private-product-passport.v4")

    def test_tampered_corporate_context_fails_closed(self):
        _, folder, meta, _ = self.build()
        result = policy.ensure_private_passport(folder, meta)
        evidence_path = folder / result["company_context_file"]
        evidence_path.write_text('{"falsely_verified":true}', "utf8")
        with self.assertRaisesRegex(ValueError, "PASSPORT_EXISTING_EVIDENCE_MISMATCH"):
            policy.ensure_private_passport(folder, meta)

    def test_cached_maker_revalidates_passport_without_rewriting(self):
        first, folder, meta, path = self.build()
        sha = policy.sha256_file(path)
        second = maker.manufacture(self.slug, self.recipes, self.out)
        self.assertFalse(second["changed"])
        self.assertEqual(second["private_passport"], first["private_passport"])
        self.assertEqual(policy.sha256_file(path), sha)
        self.assertEqual(policy.ensure_private_passport(folder, meta)["status"], "existing_verified")

    def test_tampered_passport_or_archive_fails_closed(self):
        _, folder, meta, passport = self.build()
        passport.write_text('{"fake":"signed"}', encoding="utf8")
        with self.assertRaisesRegex(ValueError, "PASSPORT_EXISTING_EVIDENCE_MISMATCH"):
            maker.manufacture(self.slug, self.recipes, self.out)
        passport.unlink()
        archive = folder / (self.slug + "-internal-qa.zip")
        archive.write_bytes(archive.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "PASSPORT_ARTIFACT_SHA_MISMATCH"):
            policy.ensure_private_passport(folder, meta)

    def test_legacy_stock_missing_source_sha_gets_incomplete_private_record(self):
        _, folder, meta, _ = self.build()
        legacy = dict(meta)
        legacy.pop("source_sha256")
        result = policy.ensure_private_passport(folder, legacy)
        self.assertIn(".source_missing.personal_owner_v4.private.json", result["passport_file"])
        p = json.loads((folder / result["passport_file"]).read_text("utf8"))
        self.assertIsNone(p["source_sha256"])
        self.assertEqual(p["source_provenance_status"],
                         "missing_original_source_sha_must_rework")
        self.assertFalse(p["commercial_release_allowed"])
        corrupt = dict(meta, source_sha256="not-a-real-hash")
        with self.assertRaisesRegex(ValueError, "PASSPORT_SOURCE_SHA_MALFORMED"):
            policy.ensure_private_passport(folder, corrupt)

    def test_public_or_unapproved_package_cannot_receive_verified_passport(self):
        _, folder, meta, _ = self.build()
        for name, value in (("public_listing_enabled", True),
                            ("owner_publication_approval", True),
                            ("price", 10), ("qa_status", "failed")):
            changed = dict(meta, **{name: value})
            with self.subTest(name=name), self.assertRaises(ValueError):
                policy.ensure_private_passport(folder, changed)

    def test_owner_declaration_does_not_fabricate_rights_or_signed_license(self):
        with self.assertRaisesRegex(ValueError, "PASSPORT_PERSONAL_OWNER_DECLARATION_ONLY"):
            policy.build_passport(self.slug, ownership=[
                {"party": "company", "percent": 60}, {"party": "person", "percent": 30}])
        with self.assertRaisesRegex(ValueError, "PASSPORT_ROLE_EVIDENCE_REQUIRED"):
            policy.build_passport(self.slug, verified_roles=["author"])
        declaration = policy.build_passport(self.slug)
        self.assertFalse(declaration["third_party_rights_cleared"])
        self.assertEqual(declaration["economic_rights"], [{
            "party": "مجتبی روزگار",
            "percent": 100,
            "status": "owner_declared_pending_title_evidence",
        }])
        self.assertFalse(declaration["company_operational_permission"]["executed_agreement_verified"])
        self.assertFalse(declaration["seller_legal_identity_and_payment_compliance_verified"])

    def test_v4_sidecar_preserves_historical_v2_and_v3_records(self):
        _, folder, meta, _ = self.build()
        v2 = folder / ("product_passport." + meta["artifact_sha256"] + ".private.json")
        v2.write_text('{"schema":"saeit.factory.private-product-passport.v2"}', encoding="utf8")
        v3 = folder / ("product_passport." + meta["artifact_sha256"] + ".personal_owner_v3.private.json")
        v3.write_text('{"schema":"saeit.factory.private-product-passport.v3"}', encoding="utf8")
        before_v2, before_v3 = v2.read_bytes(), v3.read_bytes()
        result = policy.ensure_private_passport(folder, meta)
        self.assertIn(".personal_owner_v4.private.json", result["passport_file"])
        self.assertEqual(v2.read_bytes(), before_v2)
        self.assertEqual(v3.read_bytes(), before_v3)

    def test_master_framework_covers_unlimited_future_products_without_fake_approval(self):
        for index in range(125):
            declaration = policy.build_passport("future_work_" + str(index))
            master = declaration["master_framework"]
            self.assertEqual(master["framework_id"], "ZOMOROD-MASTER-PERSONAL-RIGHTS-20261020")
            self.assertIsNone(master["product_count_cap"])
            self.assertIsNone(master["contractual_end_date"])
            self.assertFalse(master["requires_new_master_contract_for_each_product"])
            self.assertTrue(master["third_party_rights_not_automatically_transferred"])
            self.assertTrue(master["individual_product_origin_and_license_check_required"])
            self.assertFalse(master["valid_execution_and_authority_evidence_verified"])
            self.assertFalse(declaration["third_party_rights_cleared"])
            self.assertFalse(declaration["commercial_release_allowed"])
            self.assertFalse(declaration["company_operational_permission"]["executed_agreement_verified"])

    def test_backfill_existing_versions_idempotently(self):
        _, folder, meta, passport = self.build()
        passport.unlink()  # Simulate existing stock made before passport rollout.
        script = ROOT / "scripts" / "factory_private_passports_backfill_20261020.py"
        cmd = [sys.executable, str(script), "--private-root", str(self.root)]
        one = subprocess.run(cmd, capture_output=True, text=True, check=True)
        self.assertIn('"created": 1', one.stdout)
        two = subprocess.run(cmd, capture_output=True, text=True, check=True)
        self.assertIn('"existing_verified": 1', two.stdout)
        self.assertTrue(passport.is_file())

if __name__ == "__main__":
    unittest.main()
