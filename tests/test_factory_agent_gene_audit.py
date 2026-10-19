"""Advanced controls are measurable source contracts, not fictional auto-production."""
import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
P=ROOT/"scripts"/"factory_agent_gene_audit.py"
spec=importlib.util.spec_from_file_location("factory_genes",P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class FactoryAgentGeneAuditTests(unittest.TestCase):
    def test_source_module_audit_does_not_claim_live_product(self):
        result=m.audit(ROOT)
        self.assertEqual(result["schema"],m.SCHEMA)
        self.assertGreaterEqual(result["module_count"],21)
        self.assertEqual(result["syntax_or_missing_errors"],[])
        self.assertEqual(result["source_contract_genes_present"],len(m.CONTRACTS))
        self.assertEqual(result["runtime_verified_production_genes"],0)
        self.assertFalse(result["self_modifying_code"])
        self.assertFalse(result["commercial_release_granted"])
        self.assertFalse(result["site_transfer_authorized"])
    def test_known_real_execution_gaps_remain_reported(self):
        result=m.audit(ROOT)
        codes={x["id"] for x in result["known_execution_blockers"]}
        self.assertNotIn("missing_generic_work_order_executor",codes)\n        self.assertEqual(codes, {"family_dispatch_not_authorized", "missing_lifecycle_passports"})
        self.assertIn("family_dispatch_not_authorized",codes)
        self.assertIn("missing_lifecycle_passports",codes)
    def test_strict_pinned_source_contracts(self):
        actual={entry[0] for entry in m.CONTRACTS}
        for critical in ("specialist_reviewer_integrity","immutable_production_warehouse",
                         "real_product_build","resource_observation",
                         "agent_risk_registry","autonomous_decision_trace"):
            self.assertIn(critical,actual)
    def test_measured_gene_is_not_claimed_as_execution(self):
        for gene in m.audit(ROOT)["advanced_control_genes"]:
            self.assertFalse(gene["live_runtime_verified"])
            self.assertIn(gene["source_contract_status"],("present_in_source","missing"))

if __name__=="__main__":
    unittest.main()
