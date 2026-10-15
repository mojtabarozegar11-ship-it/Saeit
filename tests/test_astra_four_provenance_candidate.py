"""Reproducible four-SKU private candidate packaging regression tests."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import astra_four_provenance_candidate as audit


class FourProductProvenanceTests(unittest.TestCase):
    def example(self,location):
        base=Path(location)
        inbox=base/"private-inbox"
        inbox.mkdir()
        report={"mode":"commercial_preparation_not_store_activation",
                "owner_exclusive_rights_declared_for_four_products":True,
                "storefront_target":"mojplaywin.com",
                "publications":0,"real_checkout_transactions":0,
                "items":[]}
        prices=[("ASTRA-CIRCUIT-01","4.99","0.50"),
                ("ASTRA-PROCURE-01","19.00","1.90"),
                ("ASTRA-WATER-01","29.00","2.90"),
                ("ASTRA-ORCHARD-01","19.00","1.90")]
        for sku,normal,discounted in prices:
            pkg=sku.lower().replace("astra-","")
            mem=io.BytesIO()
            with zipfile.ZipFile(mem,"w") as z:
                z.writestr(pkg+"/README.md","# Original offline product\n")
                z.writestr(pkg+"/main.py","import json\nprint('ok')\n")
                z.writestr(pkg+"/example_synthetic.json",'{"fictional":true}')
            binary=mem.getvalue()
            digest=hashlib.sha256(binary).hexdigest()
            (inbox/(sku+"-"+digest+".zip")).write_bytes(binary)
            report["items"].append({
                "sku":sku,"builder":pkg,"title":"Astra offline product "+sku,
                "source_proof":{"artifact_sha256":digest},
                "status":"PRIVATE_COMMERCIAL_CANDIDATE_NOT_FOR_SALE",
                "owner_exclusive_rights_declared":True,
                "checkout_authorized":False,"public_listing_authorized":False,
                "quality_score":None,"suggested_list_price_usd":normal,
                "suggested_discounted_price_usd":discounted,
                "verified_technical_function":"Offline worksheet",
                "important_limits":"Independent commercial validation is pending"
            })
        catalog=base/"catalog.json"
        catalog.write_text(json.dumps(report))
        return inbox,catalog

    def test_four_reproducible_review_packages_are_private(self):
        with tempfile.TemporaryDirectory() as temp:
            inbox,catalog=self.example(temp)
            output=Path(temp)/"review"
            dry=audit.run(catalog,inbox,output,apply=False)
            self.assertEqual(dry["status"],"DRY_RUN")
            self.assertFalse(output.exists())
            first=audit.run(catalog,inbox,output,apply=True)
            self.assertEqual(len(first["items"]),4)
            self.assertEqual(len(list(output.glob("ASTRA-*.zip"))),4)
            self.assertFalse(first["paid_release_authorized"])
            for item in first["items"]:
                self.assertEqual(item["original_files_preserved"],3)
                self.assertEqual(item["supplemental_files"],3)
                self.assertEqual(item["unresolved_dependencies"],[])
                self.assertFalse(item["release_ready"])
                zip_name=item["sku"]+"-"+item["candidate_sha256"]+".zip"
                with zipfile.ZipFile(output/zip_name) as z:
                    names=z.namelist()
                    self.assertEqual(len(names),6)
                    copyright_file=next(x for x in names if x.endswith("COPYRIGHT-OWNER-DECLARATION.txt"))
                    self.assertIn("All rights reserved",z.read(copyright_file).decode())
                    provenance=next(x for x in names if x.endswith("SOURCE-PROVENANCE.json"))
                    obj=json.loads(z.read(provenance))
                    self.assertFalse(obj["legal_verification_completed"])
                    self.assertFalse(obj["dependency_review"]["paid_release_authorized"])
            second=audit.run(catalog,inbox,output,apply=True)
            self.assertTrue(all(not item["newly_written"] for item in second["items"]))
            self.assertEqual([x["candidate_sha256"] for x in first["items"]],
                             [x["candidate_sha256"] for x in second["items"]])
            self.assertEqual(len(list(output.glob("ASTRA-*.zip"))),4)
            self.assertEqual(len(list(output.glob("astra-commercial-review-*.json"))),1)

    def test_reject_tampered_original_bundle_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            inbox,catalog=self.example(temp)
            pkg=next(inbox.glob("*.zip"))
            pkg.write_bytes(b"tampered")
            output=Path(temp)/"review"
            with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
                audit.run(catalog,inbox,output,apply=True)
            self.assertFalse(output.exists())

    def test_runtime_externals_are_reported_not_automatically_cleared(self):
        source={
            "tool/main.py":b"import requests\n",
            "tool/main.js":b"import ext from 'unknown-package'; fetch('https://vendor.example')",
        }
        evidence=audit._runtime_dependency_evidence(source)
        self.assertIn("requests",evidence["unresolved_python_imports"])
        self.assertIn("unknown-package",evidence["unresolved_javascript_imports"])
        self.assertTrue(evidence["runtime_external_refs"])
        self.assertFalse(evidence["independent_license_review_complete"])

    def test_reject_archive_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"bad.zip"
            with zipfile.ZipFile(path,"w") as z:
                z.writestr("root/README.md","nice")
                z.writestr("root/main.py","print('ok')")
                z.writestr("../escape.txt","evil")
            checksum=audit.hash_bytes(path.read_bytes())
            with self.assertRaises(ValueError):
                audit.audit_zip(path,checksum)

if __name__=="__main__":
    unittest.main()
