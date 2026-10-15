"""Test private staged delivery path without Django or live payment."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from astra_mpw_stage_paid_delivery import copy_assets,validate_roots

class AstraPrivateDeliveryFiles(unittest.TestCase):
    def fixture(self,work):
        root=Path(work)
        doc=root/"mojplaywin.com";doc.mkdir()
        private=root/"private_assets";private.mkdir()
        inbox=root/"inbox";inbox.mkdir()
        products=[]
        for suffix in ("CIRCUIT","PROCURE","WATER","ORCHARD"):
            sku="ASTRA-"+suffix+"-01"
            binary=(sku+" original executable ZIP simulated data").encode()
            sha=hashlib.sha256(binary).hexdigest()
            (inbox/(sku+"-"+sha+".zip")).write_bytes(binary)
            products.append({"sku":sku,"sha256":sha})
        return doc,private,inbox,products

    def test_four_private_files_copied_and_rechecked(self):
        with tempfile.TemporaryDirectory() as d:
            doc,private,inbox,items=self.fixture(d)
            self.assertEqual(validate_roots(private,doc),private)
            initial=copy_assets(items,inbox,private,apply=False)
            self.assertEqual(sum(x["exists"] for x in initial),0)
            done=copy_assets(items,inbox,private,apply=True)
            self.assertEqual(sum(x["exists"] for x in done),4)
            self.assertEqual(sum(x["exists"] for x in copy_assets(items,inbox,private,apply=True)),4)
            self.assertEqual(len(list((private/"astra-four-specialist-v1").glob("*.zip"))),4)
            self.assertFalse((doc/"astra-four-specialist-v1").exists())

    def test_tampered_archive_does_not_copy_any(self):
        with tempfile.TemporaryDirectory() as d:
            doc,private,inbox,items=self.fixture(d)
            (inbox/(items[3]["sku"]+"-"+items[3]["sha256"]+".zip")).write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError,"SHA mismatch"):
                copy_assets(items,inbox,private,apply=True)
            self.assertFalse((private/"astra-four-specialist-v1").exists())

    def test_existing_different_archive_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            doc,private,inbox,items=self.fixture(d)
            target=private/"astra-four-specialist-v1"
            target.mkdir()
            one=items[1]
            (target/(one["sku"]+"-"+one["sha256"]+".zip")).write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError,"conflicting existing"):
                copy_assets(items,inbox,private,apply=True)
            self.assertEqual(len(list(target.glob("*.zip"))),1)

    def test_public_root_overlap_refused(self):
        with tempfile.TemporaryDirectory() as d:
            doc,private,inbox,items=self.fixture(d)
            with self.assertRaisesRegex(ValueError,"overlap"):
                validate_roots(doc,doc)
            nested=doc/"private"
            nested.mkdir()
            with self.assertRaisesRegex(ValueError,"overlap"):
                validate_roots(nested,doc)

    def test_symlinked_archive_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            doc,private,inbox,items=self.fixture(d)
            first=items[0]
            path=inbox/(first["sku"]+"-"+first["sha256"]+".zip")
            backing=inbox/"original.zip"
            path.rename(backing)
            path.symlink_to(backing)
            with self.assertRaisesRegex(ValueError,"unsafe private source"):
                copy_assets(items,inbox,private,apply=False)

if __name__=="__main__":
    unittest.main()
