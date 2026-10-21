"""Measured F19 ten-generation private customer-tool acceptance, not retail approval."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPTS=Path(__file__).resolve().parents[1]/"scripts"

def module(name,source):
    spec=importlib.util.spec_from_file_location(name,str(SCRIPTS/source))
    item=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(item)
    return item

f19=module("actual_f19_builder","factory_build50_f19_web_template.py")
fifty=module("actual_50_stage_verifier","factory_build_50.py")
ten=module("f19_ten_functionality","factory_f19_ten_generations_v1.py")

class RealF19TenGenerations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.private=Path(cls.temporary.name)
        original=f19.build(cls.private)
        assert original["completed_stages"]==50,original

    def test_01_ten_real_functional_generations_are_built_and_repeated_safely(self):
        outcome=ten.run(self.private,SCRIPTS/"factory_build_50.py")
        self.assertEqual(outcome["verified_generations"],10)
        self.assertEqual(outcome["new_generations_this_run"],10)
        self.assertFalse(outcome["quality_1000_certified"])
        self.assertFalse(outcome["commercial_release"])
        original_zip=self.private/"digital-products"/f19.PRODUCT/(f19.PRODUCT+"-internal-qa.zip")
        first_hash=ten.digest(original_zip)
        store=self.private/"quality-excellence"/"f19-ten-generations"/first_hash[:24]
        previous=first_hash
        for generation in range(1,11):
            folder=store/("g%02d"%generation)
            receipt=json.loads((folder/"receipt.json").read_text(encoding="utf8"))
            self.assertEqual(receipt["measured_tests"],generation)
            self.assertEqual(receipt["upstream_archive_sha256"],previous)
            self.assertFalse(receipt["public_listing_enabled"])
            edition=folder/(f19.PRODUCT+"-g%02d-internal-qa.zip"%generation)
            with zipfile.ZipFile(edition) as z:
                self.assertEqual(z.testzip(),None)
                for name in ten.FILES:
                    with zipfile.ZipFile(original_zip) as orig:
                        self.assertEqual(z.read(f19.PRODUCT+"/"+name),orig.read(f19.PRODUCT+"/"+name))
                code=z.read(f19.PRODUCT+"/site_tools.py").decode()
                self.assertIn("def "+["brand_personalize","page_title","meta_description","button_palette",
                    "email_contact","print_stylesheet","rtl_support","sitemap_xml","robots_txt",
                    "package_website"][generation-1],code)
            previous=receipt["archive_sha256"]
        self.assertEqual(ten.run(self.private,SCRIPTS/"factory_build_50.py")["new_generations_this_run"],0)
        self.assertEqual(first_hash,ten.digest(original_zip))

    def test_02_existing_tampered_archive_is_not_silently_approved(self):
        original_zip=self.private/"digital-products"/f19.PRODUCT/(f19.PRODUCT+"-internal-qa.zip")
        store=self.private/"quality-excellence"/"f19-ten-generations"/ten.digest(original_zip)[:24]
        archive=store/"g08"/(f19.PRODUCT+"-g08-internal-qa.zip")
        try:
            old=archive.read_bytes()
            archive.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                ten.run(self.private,SCRIPTS/"factory_build_50.py")
        finally:
            archive.write_bytes(old)

    def test_03_missing_evidence_rejects_activation(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(ValueError):
                ten.run(empty,SCRIPTS/"factory_build_50.py")
        with self.assertRaises(ValueError):
            ten.versions(11)

if __name__=="__main__":
    unittest.main()
