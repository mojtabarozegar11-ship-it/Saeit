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
    def test_missing_original_evidence_never_forces_date_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            w=Path(d);cap=w/"legal-capacity";cap.mkdir()
            (cap/"capacity-old.json").write_text("{}")
            with self.assertRaisesRegex(ValueError,"ORIGINAL_CONTRACT_EVIDENCE_NOT_PRESENT"):
                m.install(w)
            self.assertFalse(m.status(w)["contract_year_correction_ledger_verified"])
if __name__=="__main__":unittest.main()
