"""Commercial admission tests: 40 SKUs, no fake sale and real ZIP integrity."""
import hashlib,importlib.util,json,zipfile,tempfile,unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
path=BASE/"scripts/factory_commerce40_admission.py"
spec=importlib.util.spec_from_file_location("commerce40",str(path))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Commerce40Tests(unittest.TestCase):
    def test_forty_commercial_private_proposals_have_no_sales_or_approvals(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            result=m.run(root,BASE/"factory_config/forty_families.json",BASE/"scripts")
            self.assertEqual(result["private_commercial_sku_proposals"],40)
            self.assertEqual(result["genuine_verified_product_families"],0)
            self.assertEqual(result["live_products_published_by_this_engine"],0)
            self.assertEqual(len({x["sku"] for x in result["rows"]}),40)
            self.assertEqual(len(list((root/"commercial40/offers").glob("*.json"))),40)
            self.assertEqual((root/"commercial40/dashboard.json").stat().st_mode & 0o777,0o600)
            for record in result["rows"]:
                self.assertFalse(record["commercial_release"])
            self.assertEqual(m.run(root,BASE/"factory_config/forty_families.json",BASE/"scripts")["private_commercial_sku_proposals"],40)
    def test_must_verify_real_zip_and_250_member_batch_not_80_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);name="original_3d_pack"
            archive=root/(name+"-internal-qa.zip")
            with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
                for n in range(145):
                    z.writestr(name+"/asset%03d.dat"%n,"original contents "+str(n))
            checksum=m.sha(archive)
            result=m.archive_check(archive,name,checksum)
            self.assertEqual(result["members"],145)
            with self.assertRaisesRegex(ValueError,"SHA_MISMATCH"):
                m.archive_check(archive,name,"a"*64)
            with zipfile.ZipFile(archive,"w") as z:
                z.writestr(name+"/../escape.txt","attack")
            with self.assertRaisesRegex(ValueError,"UNSAFE_MEMBER"):
                m.archive_check(archive,name,m.sha(archive))
    def test_private_offer_cannot_override_absent_license_or_checkout(self):
        p=json.loads((BASE/"factory_config/forty_families.json").read_text())["profiles"][13]
        good={"product_id":"sample","technical_ok":True,"archive":{"archive_sha256":"a"*64,"members":145},"blockers":[]}
        row=m.offer(p,[good],None)
        self.assertEqual(row["technical_products_with_verified_archive"],1)
        self.assertFalse(row["public_sale_allowed"])
        self.assertFalse(row["payment_enabled"])
        self.assertIn("LICENSE_AND_PROVENANCE_RIGHTS_SIGNOFF_MISSING",row["commercial_blockers"])
        self.assertIn("PAYMENT_WEBHOOK_AND_FULFILLMENT_E2E_NOT_VERIFIED",row["commercial_blockers"])
if __name__=="__main__":unittest.main()
