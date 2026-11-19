import unittest
from prop_firm.simulation_invoice_contract import SimulationInvoiceContract, REQUIRED_GATES

class SimulationInvoiceContractTests(unittest.TestCase):
    def offer(self, kind="first"):
        return SimulationInvoiceContract("T" + "A"*33, "a"*64, kind)

    def test_first_price(self):
        self.assertEqual(self.offer().snapshot()["amount_sun"], 30_000_000)

    def test_retry_price(self):
        self.assertEqual(self.offer("retry").snapshot()["amount_sun"], 18_000_000)

    def test_simulated_principal(self):
        snapshot = self.offer().snapshot()
        self.assertEqual(snapshot["virtual_balance_usd"], 1000)
        self.assertEqual(snapshot["challenge_days"], 60)
        self.assertFalse(snapshot["virtual_principal_withdrawable"])

    def test_missing_gate(self):
        for gate in REQUIRED_GATES:
            with self.subTest(gate=gate), self.assertRaises(ValueError):
                self.offer().release({g:True for g in REQUIRED_GATES if g != gate})

    def test_retry_requires_trusted_evidence(self):
        gates = dict.fromkeys(REQUIRED_GATES, True)
        with self.assertRaises(ValueError):
            self.offer("retry").release(gates)
        self.assertEqual(self.offer("retry").release(gates, retry_eligibility_verified=True)["amount_sun"], 18_000_000)

    def test_digest_binds_purchase_kind(self):
        self.assertNotEqual(self.offer().digest(), self.offer("retry").digest())
