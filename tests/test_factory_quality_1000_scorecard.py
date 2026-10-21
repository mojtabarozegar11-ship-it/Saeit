"""No artificial 1000/1000 professional quality scores; genuine explicit threshold."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"scripts/factory_quality_1000_scorecard.py"
spec=importlib.util.spec_from_file_location("factory_1000_grade",PATH)
q=importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)

def fact(codes, family="F14"):
    return {"family_id":family,"blockers":[{"code":c} for c in codes]}

class QualityThousandTests(unittest.TestCase):
    def test_weights_exact_1000_and_twelve_noncompensatory_pillars(self):
        self.assertEqual(len(q.WEIGHTS),12)
        self.assertEqual(sum(q.WEIGHTS.values()),1000)
        self.assertEqual(q.TARGET,1000)
        self.assertEqual(set(q.WEIGHTS),{
            "global_comparative_advantage","originality_and_non_derivativeness",
            "verified_innovation","technology_and_technical_excellence",
            "domain_depth_and_accuracy","user_customer_value",
            "independent_expert_review","real_world_performance_accessibility",
            "security_ethics_regulatory_safety","legal_rights_and_provenance",
            "distribution_support_reliability","independent_adversarial_testing"})

    def test_absent_all_documentation_gets_no_document_points(self):
        issues=["P0_PROOF_MISSING:"+x for x in q.WEIGHTS]
        issues.extend(["P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING",
                       "P0_ORIGINAL_INNOVATIONS_UNPROVEN",
                       "P0_MEASURED_SUPERIORITY_UNVERIFIED"])
        card=q.grade(fact(issues))
        self.assertEqual(card["documentary_evidence_points"],0)
        self.assertEqual(card["documentary_evidence_gap"],1000)
        self.assertIsNone(card["product_quality_points"])
        self.assertFalse(card["professional_quality_1000_passed"])
        self.assertTrue(q.require_no_false_certification(card))

    def test_copying_papers_can_never_fake_certification_even_1000_documentation(self):
        card=q.grade(fact([
            "P0_INDEPENDENT_ATTESTATION_NOT_AUTHENTICATED",
            "P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED"
        ]),exact_build_sha256="f"*64,reviewer_verified=True)
        self.assertEqual(card["documentary_evidence_points"],1000)
        self.assertEqual(card["documentary_evidence_gap"],0)
        self.assertIsNone(card["product_quality_points"])
        self.assertFalse(card["independent_reviewer_authentication"])
        self.assertFalse(card["world_leading_quality_certified"])
        self.assertFalse(card["release_allowed"])
        self.assertEqual(card["disposition"],"NEEDS_INDEPENDENT_EXPERT_ASSESSMENT")

    def test_even_one_critical_pillar_blocks_noncompensatory_quality(self):
        card=q.grade(fact(["P0_PROOF_MISSING:legal_rights_and_provenance"]))
        self.assertEqual(card["documentary_evidence_points"],950)
        self.assertEqual(card["documentary_evidence_gap"],50)
        self.assertEqual(card["critical_defect_count"],1)
        self.assertFalse(card["professional_quality_1000_passed"])
        self.assertFalse(card["release_allowed"])

    def test_unverified_innovation_blocks_two_pillars_regardless_other_proofs(self):
        card=q.grade(fact(["P0_ORIGINAL_INNOVATIONS_UNPROVEN"]))
        self.assertEqual(card["documentary_evidence_points"],780)
        self.assertEqual(card["documentary_evidence_gap"],220)
        self.assertEqual(card["pillars"]["verified_innovation"]["documentary_points"],0)
        self.assertEqual(card["pillars"]["originality_and_non_derivativeness"]["documentary_points"],0)

    def test_global_5_benchmark_gap_blocks_global_advantage(self):
        card=q.grade(fact(["P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING"]))
        self.assertEqual(card["documentary_evidence_points"],880)
        self.assertFalse(card["professional_quality_1000_passed"])

    def test_domain_specialist_failure_blocks_even_full_documentary_score(self):
        card=q.grade(fact(["P0_DOMAIN_SPECIALIST_PROOF_MISSING:expert_peer_review"]),exact_build_sha256="a"*64)
        self.assertEqual(card["documentary_evidence_points"],1000)
        self.assertIn("P0_DOMAIN_SPECIALIST_PROOF_MISSING:expert_peer_review",card["specialist_gates_missing"])
        self.assertEqual(card["disposition"],"RETURN_TO_PRODUCTION_REWORK")
        self.assertEqual(card["critical_defect_count"],1)
        self.assertFalse(card["release_allowed"])

    def test_corrupt_card_or_fake_quality_approval_fails_policy(self):
        card=q.grade(fact([]))
        card["product_quality_points"]=1000
        with self.assertRaises(RuntimeError):
            q.require_no_false_certification(card)
        card=q.grade(fact([]))
        card["release_allowed"]=True
        with self.assertRaises(RuntimeError):
            q.require_no_false_certification(card)

    def test_factory_registry_sets_1000_for_all_40(self):
        import json
        data=json.loads((ROOT/"factory_config/forty_families.json").read_text(encoding="utf8"))
        self.assertEqual(len(data["profiles"]),40)
        policy=data["quality_1000_policy"]
        self.assertEqual(policy["schema"],q.SCHEMA)
        self.assertEqual(policy["minimum_verified_quality_score"],1000)
        self.assertEqual(policy["maximum_quality_score"],1000)
        self.assertEqual(policy["noncompensatory_pillars"],12)
        self.assertTrue(policy["zero_critical_defects_required"])
        self.assertTrue(policy["every_family_specialist_gate_required"])
        self.assertTrue(policy["independent_human_certification_required"])
        self.assertFalse(policy["automatic_publication_permitted"])

    def test_every_family_1000_not_auto_pass(self):
        for number in range(1,41):
            card=q.grade(fact([],family="F%02d"%number))
            self.assertEqual(card["required_points"],1000)
            self.assertIsNone(card["product_quality_points"])
            self.assertFalse(card["release_allowed"])
            self.assertEqual(card["family_id"],"F%02d"%number)

if __name__=="__main__":
    unittest.main()
