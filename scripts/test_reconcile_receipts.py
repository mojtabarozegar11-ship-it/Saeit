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
    def test_unmatched_refund(self):
        self.data["refunds"][0]["settlement_id"]="unknown"
        self.assertIn("unmatched_settlement",str(reconcile(self.data)["issues"]))
    def test_bad_money(self):
        for x in ("NaN","1e5","-1","1.234",12):
            self.assertRaises(ValueError,amount,x)
    def test_duplicate(self):
        self.data["orders"].append(self.data["orders"][0])
        self.assertRaises(ValueError,reconcile,self.data)
if __name__=="__main__": unittest.main()
