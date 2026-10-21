"""Owner year correction cannot backdate typed 1405 addenda or erase old ledger."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("year_correction",ROOT/"scripts/factory_master_contract_year_correction_1398.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class CorrectContractYear(unittest.TestCase):
    def test_separate_1398_original_and_1405_typed_revision(self):
        doc=m.original()
        self.assertEqual(doc["owner_corrected_contract_origin_year_jalali"],1398)
        self.assertEqual(doc["typed_current_wording_preparation_year_jalali"],1405)
        self.assertFalse(doc["current_additions_signed_in_1398_verified"])
        self.assertFalse(doc["commercial_approval"])
        self.assertNotEqual(m.BEFORE,m.AFTER)
    def test_append_only_amendment_does_not_rewrite_old_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            w=Path(d);cap=w/"legal-capacity";cap.mkdir()
            old=cap/"capacity-old.json"
            contents=json.dumps({"source_files":{"master_rights_1405_unsigned_draft":{"sha256":m.BEFORE}}})
            old.write_text(contents)
            item=m.install(w)
            self.assertTrue(item["preexisting_ledger_kept"])
            self.assertEqual(old.read_text(),contents)
            self.assertTrue(m.status(w)["contract_year_correction_ledger_verified"])
            before=sorted(cap.iterdir())
            again=m.install(w)
            self.assertEqual(again,item)
            self.assertEqual(before,sorted(cap.iterdir()))
    def test_owner_attests_all_current_clauses_were_signed_1398_with_no_additions(self):
        with tempfile.TemporaryDirectory() as d:
            w=Path(d);cap=w/"legal-capacity";cap.mkdir()
            (cap/"capacity-original.json").write_text(json.dumps({"original_master_sha":m.BEFORE}))
            m.install(w)
            first=m.attest_terms(w)
            self.assertTrue(first["current_terms_same_as_original_1398_owner_attested"])
            self.assertFalse(first["new_clauses_after_1398_owner_attested"])
            self.assertFalse(first["independent_signed_original_comparison"])
            self.assertFalse(first["independent_signature_verification"])
            self.assertFalse(first["sale_or_quality_clearance"])
            names=sorted(cap.iterdir())
            self.assertEqual(first,m.attest_terms(w))
            self.assertEqual(names,sorted(cap.iterdir()))
            doc=json.loads(next(cap.glob("master-terms-1398-*.json")).read_text())
            self.assertEqual(doc["typed_copy_preparation_year_jalali"],1405)
            self.assertFalse(doc["creates_new_contract_or_signatures"])
    def test_must_have_prior_year_record_before_attestation(self):
        with tempfile.TemporaryDirectory() as d:
            w=Path(d);(w/"legal-capacity").mkdir()
            with self.assertRaisesRegex(ValueError,"CORRECTED_1398_CONTRACT_YEAR_RECORD_REQUIRED"):
                m.attest_terms(w)
    def test_both_signing_capacities_owner_attested_without_invented_signatures(self):
        facts=m.dual_capacity_attestation()
        self.assertEqual(facts["contract_year_jalali"],1398)
        self.assertTrue(facts["signing_capacities_owner_attested"]["individual_personal_ip_owner"])
        self.assertTrue(facts["signing_capacities_owner_attested"]["company_managing_director_and_representative"])
        self.assertTrue(facts["same_human_signed_in_two_distinct_capacities_owner_attested"])
        self.assertFalse(facts["independently_inspected_original_signature"])
        self.assertFalse(facts["company_signing_power_officially_verified_for_1398"])
        self.assertFalse(facts["signed_qa_1000_certification_created"])
        self.assertFalse(facts["commercial_release_authorized"])
    def test_dual_capacity_receipt_requires_existing_immutable_owner_attestations(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ledger=root/"legal-capacity";ledger.mkdir()
            with self.assertRaisesRegex(ValueError,"SIGNED_1398_YEAR_AND_TERMS_OWNER_ATTESTATIONS_REQUIRED"):
                m.attest_dual_capacity(root)
            (ledger/"capacity-original.json").write_text(json.dumps({"sha256":m.BEFORE}))
            m.install(root)
            m.attest_terms(root)
            old=set(ledger.iterdir())
            first=m.attest_dual_capacity(root)
            self.assertTrue(first["owner_attested_personal_signature"])
            self.assertTrue(first["owner_attested_company_representative_signature"])
            self.assertFalse(first["independent_original_signature_verification"])
            self.assertFalse(first["official_company_authority_verified"])
            self.assertFalse(first["qa_or_commercial_approval"])
            self.assertTrue(old.issubset(set(ledger.iterdir())))
            self.assertEqual(first,m.attest_dual_capacity(root))
            self.assertEqual(len(list(ledger.glob("master-two-capacities-1398-*.json"))),1)
    def test_missing_original_evidence_never_forces_date_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            w=Path(d);cap=w/"legal-capacity";cap.mkdir()
            (cap/"capacity-old.json").write_text("{}")
            with self.assertRaisesRegex(ValueError,"ORIGINAL_CONTRACT_EVIDENCE_NOT_PRESENT"):
                m.install(w)
            self.assertFalse(m.status(w)["contract_year_correction_ledger_verified"])
if __name__=="__main__":unittest.main()
