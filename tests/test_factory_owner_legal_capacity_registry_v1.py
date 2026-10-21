"""Individual/legal person identity: existing uploaded docs, not fake legal clearance."""
import importlib.util,json,os,shutil,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
script=ROOT/"scripts/factory_owner_legal_capacity_registry_v1.py"
spec=importlib.util.spec_from_file_location("individual_company_legal_context",script)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class OwnerLegalCapacityTests(unittest.TestCase):
    def workspace(self,d):
        base=Path(d)/"quality-reviewer-console"
        base.mkdir()
        shutil.copy(ROOT/"scripts/factory_quality_reviewer_console_v1.py",
                    base/"factory_quality_reviewer_console_v1.py")
        return base
    def test_previous_real_person_and_company_are_two_separate_capacities(self):
        facts=mod.dossier()
        self.assertTrue(mod.validate(facts))
        self.assertEqual(facts["natural_person"]["legal_name_fa"],"مجتبی گلستانی‌نیک")
        self.assertEqual(facts["natural_person"]["professional_name_fa"],"مجتبی روزگار")
        self.assertEqual(facts["legal_person"]["legal_name_fa"],"شرکت کشت و صنعت زمرد ملل")
        self.assertTrue(facts["legal_person"]["legal_personality_separate_from_natural_person"])
        self.assertFalse(facts["legal_person"]["sole_owner_of_all_company_shares"])
        self.assertTrue(facts["reviewer_registration"]["one_real_person_not_two_independent_reviewers"])
        self.assertFalse(facts["real_signatures_verified"])
        self.assertEqual(facts["source_document_count"],3)
        self.assertFalse(facts["commercial_clearance_allowed"])
    def test_install_on_private_workspace_invites_owner_without_impersonation(self):
        with tempfile.TemporaryDirectory() as d:
            base=self.workspace(d)
            receipt=mod.install(base)
            self.assertEqual(receipt["owner_invitation_status"],"owner_invitation_created_without_signature")
            self.assertFalse(receipt["actual_owner_signature"])
            ledger=list((base/"legal-capacity").glob("capacity-*.json"))
            self.assertEqual(len(ledger),1)
            status=mod.audit(base)
            self.assertFalse(status["company_legal_signing_authority_verified"])
            invite=json.loads((base/"reviewer-requests"/"owner_mojtaba_roozegar.invite.json").read_text())
            self.assertEqual(invite["role"],"owner")
            self.assertFalse(invite["owner_approval"])
            same=mod.install(base)
            self.assertEqual(same["owner_invitation_status"],"owner_invitation_existing")
            self.assertEqual(len(list((base/"legal-capacity").glob("capacity-*.json"))),1)
            if os.name=="posix":self.assertEqual(ledger[0].stat().st_mode&0o777,0o600)
    def test_1398_documents_do_not_auto_sign_1405_contract(self):
        record=mod.dossier()
        self.assertTrue(record["source_files"]["company_memo_user_supplied_1398_claim"]["original_historical_execution_owner_attested"])
        self.assertFalse(record["source_files"]["master_rights_1405_unsigned_draft"]["signed_or_executed"])
        self.assertFalse(record["legal_relationship"]["master_contract_rewrite_signed_and_executed"])
    def test_upgrading_unverified_claim_to_verified_is_rejected(self):
        doc=mod.dossier()
        doc["legal_person"]["current_signatory_authority_officially_verified"]=True
        with self.assertRaisesRegex(ValueError,"TAMPER_OR_UNAUTHORIZED"):
            mod.validate(doc)
        doc=mod.dossier()
        doc["reviewer_registration"]["natural_person_owner_signature_available"]=True
        with self.assertRaisesRegex(ValueError,"TAMPER_OR_UNAUTHORIZED"):
            mod.validate(doc)
    def test_no_public_pii_ids_or_signature_bytes_in_private_record(self):
        doc=mod.dossier();raw=json.dumps(doc,ensure_ascii=False)
        self.assertNotIn("national_personal_id_number",raw)
        self.assertNotIn("BEGIN PRIVATE KEY",raw)
        self.assertNotIn("۷۳۷۱۶۴۷۹۷۷",raw)
        self.assertNotIn("خیابان قدس",raw)
    def test_missing_review_console_prevents_false_owner_invitation(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)/"workspace"
            with self.assertRaisesRegex(ValueError,"REVIEWER_CONSOLE_NOT_DEPLOYED"):
                mod.install(base)
            self.assertEqual(len(list((base/"legal-capacity").glob("capacity-*.json"))),1)
            self.assertFalse(mod.audit(base)["release_allowed"])
if __name__=="__main__":unittest.main()
