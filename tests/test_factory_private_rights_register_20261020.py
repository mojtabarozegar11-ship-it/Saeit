import importlib.util,json,hashlib
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1]/"scripts/factory_private_rights_register_20261020.py"
spec=importlib.util.spec_from_file_location("rights",P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RightsAudit(unittest.TestCase):
 def test_hashbound_registry_is_not_license(self):
  recipe="fieldwork_vector_illustration_suite";sha="a"*64
  files=[{"name":recipe+"/drawing%03d.svg"%i,"sha256":"b"*64,"bytes":25} for i in range(96)]
  files.append({"name":recipe+"/permissions_foundation.pdf","sha256":"c"*64,"bytes":200})
  doc=m.document(recipe,sha,{"original_zip_sha256":sha,"files":files})
  self.assertEqual(doc["asset_count"],97)
  self.assertEqual(len(doc["candidate_rights_named_files"]) if "candidate_rights_named_files" in doc else
                   sum(a["potential_rights_document_filename"] for a in doc["assets"]),1)
  self.assertFalse(doc["claimant_chain_of_title_verified"])
  self.assertFalse(doc["independent_legal_review_signed"])
  self.assertFalse(doc["owner_publication_approval"])
  self.assertFalse(doc["commercial_distribution_allowed"])
  self.assertFalse(doc["assets"][96]["redistribution_permission_verified"])
  self.assertEqual(m.hashbytes(m.dump(doc)),hashlib.sha256(m.dump(doc)).hexdigest())
 def test_wrong_hash_or_missing_asset_fails_closed(self):
  recipe="fieldwork_arithmetic_teacher_kits";sha="a"*64
  src=[{"name":recipe+"/item%d.txt"%i,"sha256":"b"*64,"bytes":8} for i in range(97)]
  with self.assertRaisesRegex(ValueError,"RIGHTS_SOURCE_INDEX_MISMATCH"):
   m.document(recipe,"c"*64,{"original_zip_sha256":sha,"files":src})
  src[20]["sha256"]="INVALID"
  with self.assertRaisesRegex(ValueError,"RIGHTS_UNTRUSTED_ASSET"):
   m.document(recipe,sha,{"original_zip_sha256":sha,"files":src})
if __name__=="__main__":unittest.main()
