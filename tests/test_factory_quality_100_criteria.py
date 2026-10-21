"""Regression: exactly 100 meaningful checks, each 10 points; no false green."""
import hashlib,importlib.util,json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/"scripts/factory_quality_1000_v2.py"
spec=importlib.util.spec_from_file_location("score100",FILE)
score=importlib.util.module_from_spec(spec);spec.loader.exec_module(score)
def verdict(errors=(),family="F14"):
    return {"family_id":family,"blockers":[{"code":c} for c in errors]}
def attach(root,key,text):
    f=root/(key+".txt")
    f.write_text((text+" with raw byte evidence for integrity review; ")*2)
    return {"path":f.name,"sha256":hashlib.sha256(f.read_bytes()).hexdigest()}

class OneHundredTimesTen(unittest.TestCase):
    def test_exactly_one_hundred_distinct_criteria_all_ten(self):
        self.assertEqual(len(score.CRITERIA),100)
        self.assertEqual({c["group"] for c in score.CRITERIA.values()},set(score.LINK))
        self.assertEqual(len(set(x["name"] for x in score.CRITERIA.values())),100)
        self.assertEqual(list(score.CRITERIA),["Q%03d"%n for n in range(1,101)])
        self.assertEqual(sum(10 for _ in score.CRITERIA),1000)
        self.assertEqual(len(score.LINK),10)

    def test_active_policy_applies_to_all_forty_families(self):
        policy=json.loads((ROOT/"factory_config/active_quality_1000_policy.json").read_text())
        registry=json.loads((ROOT/"factory_config/forty_families.json").read_text())
        self.assertTrue(policy["active"])
        self.assertEqual(policy["scope"],"all_40_registered_families")
        self.assertEqual(policy["count"],100)
        self.assertEqual(policy["points_per_criterion"],10)
        self.assertEqual(policy["total_required"],1000)
        self.assertEqual(len(registry["profiles"]),40)

    def test_no_uploaded_evidence_results_in_zero_documentary_points(self):
        for family in ("F01","F14","F28","F40"):
            c=score.grade(verdict(family=family))
            self.assertEqual(c["documentary_evidence_points"],0)
            self.assertIsNone(c["product_quality_points"])
            self.assertFalse(c["release_allowed"])
            self.assertEqual(c["criteria_count"],100)
            self.assertTrue(score.require_no_false_certification(c))

    def test_one_evidence_is_ten_points_and_corruption_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);e=attach(root,"Q001","real report")
            q=score.grade(verdict(),criteria_evidence={"Q001":e},evidence_root=root)
            self.assertEqual(q["documentary_evidence_points"],10)
            self.assertEqual(q["documentary_evidence_gap"],990)
            (root/"Q001.txt").write_text("modified after sha computed")
            changed=score.grade(verdict(),criteria_evidence={"Q001":e},evidence_root=root)
            self.assertEqual(changed["documentary_evidence_points"],0)

    def test_one_critical_blocker_disqualifies_even_if_documents_exist(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            evidence={k:attach(root,k,"supporting research") for k in score.CRITERIA}
            clean=score.grade(verdict(),criteria_evidence=evidence,evidence_root=root)
            self.assertEqual(clean["documentary_evidence_points"],1000)
            self.assertIsNone(clean["product_quality_points"])
            self.assertFalse(clean["release_allowed"])
            blocked=score.grade(verdict(["P0_PROOF_MISSING:legal_rights_and_provenance"]),
                                criteria_evidence=evidence,evidence_root=root)
            self.assertLess(blocked["documentary_evidence_points"],1000)
            self.assertGreaterEqual(blocked["critical_defect_count"],1)
            self.assertFalse(blocked["professional_quality_1000_passed"])

    def test_fake_expert_approval_cannot_raise_real_quality_to_1000(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            evidence={k:attach(root,k,"unverified written review") for k in score.CRITERIA}
            c=score.grade(verdict(),criteria_evidence=evidence,evidence_root=root,
                          reviewer_verified=True,exact_build_sha256="b"*64)
            self.assertEqual(c["documentary_evidence_points"],1000)
            self.assertIsNone(c["product_quality_points"])
            self.assertFalse(c["independent_reviewer_authentication"])
            self.assertFalse(c["release_allowed"])
            c["product_quality_points"]=1000
            with self.assertRaises(RuntimeError):score.require_no_false_certification(c)

    def test_global_novelty_and_competitor_defects_cancel_respective_items(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            evidence={k:attach(root,k,"test") for k in score.CRITERIA}
            c=score.grade(verdict(["P0_GLOBAL_TOP_FIVE_CURRENT_BENCHMARKS_MISSING",
                                   "P0_ORIGINAL_INNOVATIONS_UNPROVEN"]),
                          criteria_evidence=evidence,evidence_root=root)
            self.assertEqual(c["criteria"]["Q002"]["documentary_points"],0)
            self.assertEqual(c["criteria"]["Q013"]["documentary_points"],0)
            self.assertEqual(c["criteria"]["Q014"]["documentary_points"],0)
            self.assertLess(c["documentary_evidence_points"],1000)

    def test_specialist_blocker_cannot_be_overridden_by_1000_documents(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            evidence={k:attach(root,k,"expert report") for k in score.CRITERIA}
            c=score.grade(verdict(["P0_DOMAIN_SPECIALIST_PROOF_MISSING:expert_peer_review"]),
                          criteria_evidence=evidence,evidence_root=root)
            self.assertEqual(c["documentary_evidence_points"],1000)
            self.assertEqual(c["critical_defect_count"],1)
            self.assertFalse(c["professional_quality_1000_passed"])
            self.assertEqual(c["disposition"],"RETURN_TO_PRODUCTION_REWORK")

if __name__=="__main__":unittest.main()
