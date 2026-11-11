"""Rights metadata linkage must be fail-closed; no DB or customer records."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE=Path(__file__).resolve().parents[1]/"services/mpw_trx_commercial_context.py"
SPEC=importlib.util.spec_from_file_location("mpw_rights_context",SOURCE)
CONTEXT=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTEXT)


def evidence():
    sha="abc123"*10+"abcd"
    return {"rights_cleared":True,"publication_approved":True,
            "sha256":sha,"rights_asset_sha256":sha,
            "rights_document_sha256":"f"*64}


class RightsMetadataContract(unittest.TestCase):
    def test_exact_document_and_artifact_linkage(self):
        fields=evidence()
        self.assertTrue(CONTEXT.rights_cleared_for_sale(SimpleNamespace(metadata=fields)))
        fields["rights_asset_sha256"]=fields["sha256"].upper()
        self.assertTrue(CONTEXT.rights_cleared_for_sale(SimpleNamespace(metadata=fields)))

    def test_unverified_rights_or_publication_cannot_pass(self):
        for key in ("rights_cleared","publication_approved"):
            for bad in (False,"true",1,None):
                with self.subTest(key=key,value=bad):
                    fields=evidence()
                    fields[key]=bad
                    self.assertFalse(CONTEXT.rights_cleared_for_sale(SimpleNamespace(metadata=fields)))

    def test_missing_malformed_or_mismatched_hash_fails_closed(self):
        for key in ("sha256","rights_asset_sha256","rights_document_sha256"):
            for value in (None,"", "f"*63,"z"*64,123):
                with self.subTest(key=key,value=value):
                    fields=evidence()
                    fields[key]=value
                    self.assertFalse(CONTEXT.rights_cleared_for_sale(SimpleNamespace(metadata=fields)))
        fields=evidence()
        fields["rights_asset_sha256"]="1"*64
        self.assertFalse(CONTEXT.rights_cleared_for_sale(SimpleNamespace(metadata=fields)))

    def test_non_dict_metadata_and_missing_product_do_not_pass(self):
        for product in (None,SimpleNamespace(metadata=None),SimpleNamespace(metadata=[]),
                        SimpleNamespace(metadata={})):
            self.assertFalse(CONTEXT.rights_cleared_for_sale(product))


if __name__=="__main__":
    unittest.main()
