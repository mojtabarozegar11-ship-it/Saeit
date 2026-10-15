"""Astra owner-attested four private store draft intake tests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"astra_mpw_four_draft_import.py"
spec=importlib.util.spec_from_file_location("astra_four_import_tests",SCRIPT)
tool=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class FourDraftPreparationTests(unittest.TestCase):
    def make(self,location):
        base=Path(location)
        packages=base/"packages"
        packages.mkdir()
        catalog={"mode":"commercial_preparation_not_store_activation",
                 "owner_exclusive_rights_declared_for_four_products":True,
                 "storefront_target":"mojplaywin.com","publications":0,
                 "real_checkout_transactions":0,"items":[]}
        choices=[("ASTRA-ORCHARD-01","19.00","1.90"),
                 ("ASTRA-PROCURE-01","19.00","1.90"),
                 ("ASTRA-WATER-01","29.00","2.90"),
                 ("ASTRA-CIRCUIT-01","4.99","0.50")]
        for sku,listprice,discounted in choices:
            content=(sku+" private source package").encode()
            digest=hashlib.sha256(content).hexdigest()
            (packages/(sku+"-"+digest+".zip")).write_bytes(content)
            catalog["items"].append({
                "sku":sku,"builder":"private_"+sku.lower(),
                "title":"Astra original specialist product "+sku,
                "source_proof":{"artifact_sha256":digest},
                "status":"PRIVATE_COMMERCIAL_CANDIDATE_NOT_FOR_SALE",
                "owner_exclusive_rights_declared":True,
                "checkout_authorized":False,"public_listing_authorized":False,
                "quality_score":None,"suggested_list_price_usd":listprice,
                "suggested_discounted_price_usd":discounted,
                "verified_technical_function":"Offline testable reference package",
                "important_limits":"Not yet independently commercially tested",
            })
        manifest=base/"commercial-catalog.json"
        manifest.write_text(json.dumps(catalog))
        return manifest,packages

    def test_four_valid_inactive_import_specs(self):
        with tempfile.TemporaryDirectory() as d:
            manifest,packages=self.make(d)
            rows=tool.verify_store_bundle(manifest,packages)
            self.assertEqual({r["sku"] for r in rows},tool.EXPECTED_SKUS)
            self.assertEqual({r["sale_usd"] for r in rows},{"1.90","2.90","0.50"})
            self.assertTrue(all(len(r["sha256"])==64 for r in rows))

    def test_modified_content_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            manifest,packages=self.make(d)
            one=next(packages.glob("*.zip"))
            one.write_bytes(b"tamper")
            with self.assertRaisesRegex(ValueError,"sha not verified"):
                tool.verify_store_bundle(manifest,packages)

    def test_owner_attestation_required(self):
        with tempfile.TemporaryDirectory() as d:
            manifest,packages=self.make(d)
            data=json.loads(manifest.read_text())
            data["owner_exclusive_rights_declared_for_four_products"]=False
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"owner-attested"):
                tool.verify_store_bundle(manifest,packages)

    def test_cannot_import_public_checkout_flag(self):
        with tempfile.TemporaryDirectory() as d:
            manifest,packages=self.make(d)
            data=json.loads(manifest.read_text())
            data["items"][0]["checkout_authorized"]=True
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"not matched"):
                tool.verify_store_bundle(manifest,packages)

    def test_duplicate_sku_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            manifest,packages=self.make(d)
            data=json.loads(manifest.read_text())
            data["items"][1]["sku"]=data["items"][0]["sku"]
            manifest.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                tool.verify_store_bundle(manifest,packages)

    def test_no_payment_or_store_api_calls(self):
        content=SCRIPT.read_text()
        self.assertNotIn("PaymentIntent.objects.create",content)
        self.assertNotIn("Order.objects.create",content)
        self.assertNotIn("active=True",content)
        self.assertNotIn("urllib.request",content)


if __name__=="__main__":
    unittest.main()
