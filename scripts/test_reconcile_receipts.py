import unittest
from reconcile_receipts import reconcile, amount

class TestSettlement(unittest.TestCase):
    def setUp(self):
        self.data={"currency":"USD","orders":[{"id":"o","amount":"30.00","status":"paid","delivery_confirmed":True}],
        "settlements":[{"id":"s","order_id":"o","amount":"30.00","status":"settled","reference":"bank-ref"}],
        "refunds":[{"id":"r","settlement_id":"s","amount":"5.00","status":"completed"}]}
    def test_net_not_certified(self):
        x=reconcile(self.data)
        self.assertEqual(x["net_settled_unverified"],"25.00")
        self.assertFalse(x["revenue_certified"])
        self.assertEqual(x["issues"],[])
    def test_paid_without_settlement(self):
        self.data["settlements"]=[]
        self.assertIn("paid_claim_not_fully_settled",str(reconcile(self.data)["issues"]))
    def test_overpayment(self):
        self.data["settlements"][0]["amount"]="31.00"
        self.assertIn("settlements_exceed_order",str(reconcile(self.data)["issues"]))
    def test_excessive_refund_does_not_make_net_negative(self):
        self.data["refunds"][0]["amount"]="35.00"
        result=reconcile(self.data)
        self.assertEqual(result["completed_refunds_unverified"],"0")
        self.assertEqual(result["net_settled_unverified"],"30.00")
        self.assertIn("refund_exceeds_settlement",str(result["issues"]))
    def test_cumulative_refunds_cannot_exceed_settlement(self):
        self.data["refunds"].append({"id":"r2","settlement_id":"s","amount":"26.00","status":"completed"})
        result=reconcile(self.data)
        self.assertEqual(result["completed_refunds_unverified"],"5.00")
        self.assertEqual(result["net_settled_unverified"],"25.00")
        self.assertIn("refund_exceeds_settlement",str(result["issues"]))
    def test_unmatched_refund(self):
        self.data["refunds"][0]["settlement_id"]="unknown"
        self.assertIn("unmatched_settlement",str(reconcile(self.data)["issues"]))
    def test_refund_for_unrecognized_settlement_does_not_reduce_net(self):
        self.data["settlements"][0]["order_id"] = "missing"
        result = reconcile(self.data)
        self.assertEqual(result["gross_settled_unverified"], "0")
        self.assertEqual(result["completed_refunds_unverified"], "0")
        self.assertEqual(result["net_settled_unverified"], "0")
        self.assertIn("unmatched_settlement", str(result["issues"]))
        self.assertFalse(result["revenue_certified"])
    def test_duplicate_external_reference_not_counted_twice(self):
        self.data["orders"].append({"id":"o2","amount":"30.00","status":"paid","delivery_confirmed":False})
        self.data["settlements"].append({"id":"s2","order_id":"o2","amount":"30.00","status":"settled","reference":"bank-ref"})
        result = reconcile(self.data)
        self.assertEqual(result["gross_settled_unverified"],"30.00")
        self.assertEqual(result["net_settled_unverified"],"25.00")
        self.assertIn("duplicate_external_reference",str(result["issues"]))
        self.assertIn("paid_claim_not_fully_settled",str(result["issues"]))
    def test_invalid_unpaid_order_amount_rejected(self):
        self.data["orders"].append({"id":"unpaid","amount":"NaN","status":"pending","delivery_confirmed":False})
        self.assertRaises(ValueError,reconcile,self.data)
    def test_missing_unpaid_order_amount_rejected(self):
        self.data["orders"].append({"id":"unpaid","status":"pending","delivery_confirmed":False})
        self.assertRaises(ValueError,reconcile,self.data)
    def test_mismatched_currency_rejected_in_all_record_types(self):
        for key in ("orders", "settlements", "refunds"):
            with self.subTest(key=key):
                self.data[key][0]["currency"] = "EUR"
                self.assertRaises(ValueError, reconcile, self.data)
                self.data[key][0].pop("currency")
    def test_matching_currency_case_insensitive(self):
        self.data["settlements"][0]["currency"] = "usd"
        self.assertEqual(reconcile(self.data)["net_settled_unverified"], "25.00")
    def test_bad_money(self):
        for x in ("NaN","1e5","-1","1.234",12):
            self.assertRaises(ValueError,amount,x)
    def test_duplicate(self):
        self.data["orders"].append(self.data["orders"][0])
        self.assertRaises(ValueError,reconcile,self.data)
if __name__=="__main__": unittest.main()
