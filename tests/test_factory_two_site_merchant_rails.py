"""Exactly-two merchant rails across all 40 factory families; no fake settlements."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
DIR=Path(__file__).resolve().parents[1]/"scripts"
spec=importlib.util.spec_from_file_location("merchantrails",str(DIR/"factory_two_site_merchant_rails.py"))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def seed(root):
    offers=root/"commercial40/offers";offers.mkdir(parents=True)
    for i in range(1,41):
        fid="F%02d"%i
        data={"family_id":fid,"sku":"SM-"+fid,"offer_status":"commercial_preparation_private_only",
          "public_sale_allowed":False,"payment_enabled":False,"published":False,
          "technical_products_with_verified_archive":1 if i<=28 else 0,
          "commercial_blockers":["LICENSE_SIGNOFF","PAYMENT_SETTLEMENT_E2E_UNVERIFIED"]}
        (offers/(fid+".json")).write_text(json.dumps(data),encoding="utf8")
    summary={"private_commercial_sku_proposals":40,"commercially_approved_families":0,
      "genuine_verified_product_families":28,"families_without_trusted_package":12}
    (root/"commercial40/dashboard.json").write_text(json.dumps(summary),encoding="utf8")
class TwoSiteMerchantRails(unittest.TestCase):
 def test_all_40_different_for_each_site_exactly_80_private_routes(self):
    with tempfile.TemporaryDirectory() as tmp:
      root=Path(tmp);seed(root)
      result=m.run(root)
      self.assertEqual(result["private_site_family_offer_routes"],80)
      self.assertEqual(result["site_count"],2)
      self.assertEqual(len({(x["site_id"],x["family_id"]) for x in result["route_records"]}),80)
      crypto=m.load(root/"merchant-rails/routes/mojplaywin/F18.json")
      shahr=m.load(root/"merchant-rails/routes/zomorodmelal/F18.json")
      self.assertEqual(crypto["settlement_type"],"on_chain")
      self.assertEqual(crypto["permitted_settlement_currencies"],["TRX","ETH"])
      self.assertEqual(shahr["settlement_type"],"bank_psp_server_to_server_verify")
      self.assertEqual(shahr["bank_account_provider"],"Bank Shahr")
      self.assertEqual(shahr["permitted_settlement_currencies"],["IRR"])
      self.assertEqual(shahr["psp_provider"],"not_yet_verified")
      for route in (crypto,shahr):
          self.assertEqual(route["declared_seller_type"],"natural_person_owner_not_company")
          self.assertEqual(route["declared_seller_professional_name"],"مجتبی روزگار")
          self.assertFalse(route["legal_seller_identity_independently_verified"])
          self.assertFalse(route["merchant_gateway_contract_matches_declared_seller"])
          self.assertFalse(route["settlement_beneficiary_matches_declared_seller_verified"])
          self.assertIn("services_platform",route["company_role"])
      self.assertFalse(shahr["collect_customer_payment"])
      self.assertFalse(crypto["automatic_paid_entitlement"])
      self.assertFalse(result["bank_shahr_gateway_psp_verified"])
      self.assertEqual((root/"merchant-rails/dashboard.json").stat().st_mode&0o777,0o600)
 def test_merchant_can_never_accept_wrong_site_currency(self):
    self.assertEqual(m.require_currency("mojplaywin","TRX"),"TRX")
    self.assertEqual(m.require_currency("zomorodmelal","IRR"),"IRR")
    for site,currency in [("mojplaywin","IRR"),("zomorodmelal","TRX"),
                          ("zomorodmelal","ETH"),("mojplaywin","USD")]:
      with self.assertRaisesRegex(ValueError,"CURRENCY_SITE_MISMATCH"):
        m.require_currency(site,currency)
 def test_site_origin_rejects_userinfo_redirect_and_fake_bank_hosts(self):
    self.assertEqual(m.assert_origin("zomorodmelal","https://zomorodmelal.ir/"),"zomorodmelal")
    for host in ("https://zomorodmelal.ir.evil.example/",
       "https://evil.example@zomorodmelal.ir/","http://zomorodmelal.ir/",
       "https://mojplaywin.com/"):
      with self.assertRaisesRegex(ValueError,"INVALID_SITE_ORIGIN"):
        m.assert_origin("zomorodmelal",host)
 def test_client_claimed_payment_cannot_unlock_any_receipt(self):
    with tempfile.TemporaryDirectory() as tmp:
      root=Path(tmp);seed(root);m.run(root)
      for site in m.SITES:
        item=m.load(root/"merchant-rails/routes"/site/"F24.json")
        for bogus in ({"status":"paid","tx":"synthetic"},None,{"amount":99999999}):
          with self.assertRaisesRegex(ValueError,"NO_AUTHENTICATED_PROVIDER_RECEIPT_VERIFIER"):
            m.reject_unverified_payment(item,bogus)
 def test_merchant_account_never_inherits_public_or_unreviewed_sale_flag(self):
    with tempfile.TemporaryDirectory() as tmp:
      root=Path(tmp);seed(root)
      p=root/"commercial40/offers/F07.json"
      j=json.loads(p.read_text());j["payment_enabled"]=True;p.write_text(json.dumps(j))
      with self.assertRaisesRegex(ValueError,"INVALID_COMMERCIAL_STATE"):
        m.run(root)
if __name__=="__main__":unittest.main()
