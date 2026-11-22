"""Independent source sales-scope checks; no network access or real customer data."""
from pathlib import Path
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"ops/revenue/mojtaba_sales_scope_validate_v1.py"
SPEC=importlib.util.spec_from_file_location("sales_scope_check",SCRIPT)
M=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=M;SPEC.loader.exec_module(M)
REG=M.loads_unique((ROOT/M.OFFER_FILE).read_text("utf-8"))
MAN=M.loads_unique((ROOT/M.MANIFEST).read_text("utf-8"))

class BriefContractTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.result=M.check(ROOT)
 def mutated(self):
  return copy.deepcopy(REG),copy.deepcopy(MAN)
 def test_01_all_eleven_source_scopes_validate(self):
  self.assertEqual(self.result["source_scopes_checked"],11)
 def test_02_exact_canonical_bot(self):
  self.assertEqual(self.result["canonical_bot_id"],"mojtaba.bot.ai")
 def test_03_no_actual_revenue_assumed(self):
  self.assertIsNone(self.result["received_revenue_verified"])
 def test_04_no_leads_assumed(self):
  self.assertIsNone(self.result["live_customer_inquiries_verified"])
 def test_05_no_sales_assumed(self):
  self.assertIsNone(self.result["paid_sales_verified"])
 def test_06_zero_side_effects(self):
  for x in ("customer_messages_sent","orders_created","payments_triggered","production_writes"):
   self.assertEqual(self.result[x],0)
 def test_07_no_private_information(self):
  self.assertFalse(self.result["customer_information_accessed"])
 def test_08_no_scope_can_claim_live_delivery(self):
  self.assertFalse(any(row["verified_live_delivery"] for row in self.result["scopes"]))
 def test_09_all_source_contracts(self):
  self.assertEqual(self.result["source_scope_contract_pass_count"],11)
 def test_10_each_scope_is_unique(self):
  ids=[row["id"] for row in self.result["scopes"]]
  self.assertEqual(len(ids),len(set(ids)))
 def test_11_index_links_are_complete(self):
  index=(ROOT/M.INDEX).read_text("utf-8")
  self.assertEqual(sum(index.count("./"+row["id"]+".md") for row in self.result["scopes"]),11)
 def test_12_only_inquiry_candidates_get_paid_scope_briefs(self):
  indexed={r["offer_id"] for r in MAN["briefs"]}
  blocked={o["offer_id"] for o in REG["offers"] if o["stage"]=="release_blocked"}
  self.assertTrue(indexed.isdisjoint(blocked))
 def test_13_free_product_not_misrepresented_as_paid_service(self):
  self.assertNotIn("free_wheat_tool",{r["offer_id"] for r in MAN["briefs"]})
 def test_14_registry_rejects_missing_draft_brief(self):
  a,b=self.mutated();b["briefs"].pop()
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_15_duplicate_brief_rejected(self):
  a,b=self.mutated();b["briefs"][1]=b["briefs"][0]
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_16_bot_alias_rejected(self):
  a,b=self.mutated();b["canonical_bot_id"]="second-bot"
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_17_fake_sale_approval_rejected(self):
  a,b=self.mutated();a["offers"][0]["owner_approved"]=True
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_18_fake_price_rejected(self):
  a,b=self.mutated();a["offers"][0]["price_irr"]=3000000
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_19_payment_enabled_rejected(self):
  a,b=self.mutated();a["offers"][0]["payment_enabled"]=True
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_20_fake_delivery_rejected(self):
  a,b=self.mutated();a["offers"][0]["delivery_verified"]=True
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_21_fake_live_presence_rejected(self):
  a,b=self.mutated();a["offers"][0]["public_live_verified"]=True
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_22_wrong_offer_scope_rejected(self):
  a,b=self.mutated();b["briefs"][0]["offer_id"]="digital_publications"
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_23_missing_source_provenance_rejected(self):
  a,b=self.mutated();a["offers"][0]["source_files"]=["a_nonexistent_source.md"]
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_24_duplicate_json_keys_rejected(self):
  with self.assertRaises(M.BriefInvalid):M.loads_unique('{"a":1,"a":2}')
 def test_25_path_traversal_rejected(self):
  with self.assertRaises(M.BriefInvalid):M.safe_file(ROOT,"../private/file")
 def test_26_absolute_path_rejected(self):
  with self.assertRaises(M.BriefInvalid):M.safe_file(ROOT,"/etc/passwd")
 def test_27_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/"real.md").write_text("hi");(root/"link.md").symlink_to(root/"real.md")
   with self.assertRaises(M.BriefInvalid):M.safe_file(root,"link.md")
 def test_28_missing_path_rejected(self):
  with self.assertRaises(M.BriefInvalid):M.safe_file(ROOT,"docs/sales/mojtaba-20261114/unknown.md")
 def test_29_injection_in_path_rejected(self):
  with self.assertRaises(M.BriefInvalid):M.safe_file(ROOT,"docs/sales/file\nhttps://evil")
 def test_30_mismatched_required_input_rejected(self):
  a,b=self.mutated();a["offers"][0]["required_inputs"]=["An impossible unique input string"]
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_31_mismatched_deliverable_rejected(self):
  a,b=self.mutated();a["offers"][0]["deliverables"]=["Uninvented unique final output"]
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_32_mismatched_exclusion_rejected(self):
  a,b=self.mutated();a["offers"][0]["exclusions"]=["Uninvented unique exclusion"]
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_33_unrecognized_manifest_field_rejected(self):
  a,b=self.mutated();b["unverified_total_sales"]=90000
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_34_missing_scope_intent_rejected(self):
  a,b=self.mutated();b["scope"]="approved_for_release"
  with self.assertRaises(M.BriefInvalid):M.check(ROOT,a,b)
 def test_35_mismatched_priority_allowed_only_if_price_still_blocked(self):
  a,b=self.mutated();a["offers"][0]["priority_band"]=4
  self.assertEqual(M.check(ROOT,a,b)["source_scopes_checked"],11)
 def test_36_cli_output_has_no_prospect_pii(self):
  p=subprocess.run([sys.executable,"-B",str(SCRIPT)],capture_output=True,text=True,timeout=12)
  self.assertEqual(p.returncode,0,p.stderr)
  o=json.loads(p.stdout)
  self.assertNotIn("email",str(o).lower())
  self.assertNotIn("customer_phone",str(o).lower())
 def test_37_cli_bad_root_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   p=subprocess.run([sys.executable,"-B",str(SCRIPT),"--repo-root",d],capture_output=True,text=True,timeout=12)
  self.assertEqual(p.returncode,2)
  self.assertEqual(json.loads(p.stdout)["status"],"BLOCKED")

if __name__=="__main__":unittest.main()
