"""Fail-closed, network-free factory research evidence quality tests."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "saeit_factory_evidence_quality",str(ROOT/"scripts"/"factory_evidence_quality.py"))
quality=importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


def synthetic_bundle():
    hosts=["www.fao.org","www.ers.usda.gov","www.worldbank.org",
           "www.ifpri.org","www.oecd.org"]
    sources=[{"id":i+1,"url":"https://"+host+"/reference/"+str(i),"publisher":host}
             for i,host in enumerate(hosts)]
    evidence=[]
    for i in range(100):
        evidence.append({
            "source_id": i%5+1,
            "confidence":"0.85",
            "passage":"Synthetic test datum %03d: " % i +
                "This text is a placeholder test record, not a real scientific source or"
                " confirmation of any market-demand, production-cost, or profit estimate."
        })
    return {
        "product_id":42,
        "sources":sources,
        "evidence":evidence,
        "internal_actions":[{
            "action_id":"factory-verification-0001",
            "verified":True,
            "evidence_sha256":"a"*64,
            "outcome":"Synthetic offline regression action, not a real industry observation.",
        }],
        "issues":[],
        "validation_outcome":"PASS",
        "missing_factors":[],
    }


class FactoryEvidenceQualityTests(unittest.TestCase):
    def test_sparse_realistic_factory_draft_is_blocked(self):
        b={"product_id":1,"sources":[{"id":1,"url":"https://fao.org/data"}],
           "evidence":[{"source_id":1,"passage":"short","confidence":"0.80"}],
           "issues":["MISSING_PRODUCT_OWNER","NO_POSITIVE_PRICE",
                     "NO_APPROVED_KNOWLEDGE_ARTICLE"],
           "missing_factors":list(quality.REQUIRED_FACTORS),
           "validation_outcome":"NEEDS_MORE_EVIDENCE"}
        result=quality.assess(b)
        self.assertFalse(result["research_gate_passed"])
        self.assertFalse(result["publish_authorized"])
        self.assertEqual(result["counts"]["validated_unique_evidence_passages"],0)
        self.assertEqual(result["counts"]["public_distinct_domain_groups"],1)
        self.assertEqual(result["counts"]["upstream_factors_marked_missing"],10)
        self.assertIn("TEN_FACTOR_VALIDATION_PASS_REQUIRED",result["blockers"])

    def test_hundred_structured_records_only_qualify_for_independent_review(self):
        r=quality.assess(synthetic_bundle())
        self.assertTrue(r["research_gate_passed"])
        self.assertEqual(r["research_gate"],"QUANTITATIVE_THRESHOLD_MET_REVIEW_REQUIRED")
        self.assertEqual(r["counts"]["validated_unique_evidence_passages"],100)
        self.assertEqual(r["counts"]["public_distinct_domain_groups"],5)
        self.assertFalse(r["publish_authorized"])
        self.assertFalse(r["commercial_quality_approved"])
        self.assertFalse(r["price_review_completed"])
        self.assertFalse(r["verified_sales"])
        self.assertIn("HUMAN_COMMERCIAL_LICENSE_AND_FACTUAL_REVIEW_REQUIRED",r["blockers"])

    def test_duplicated_evidence_does_not_inflate_count(self):
        b=synthetic_bundle()
        b["evidence"]=[b["evidence"][0]]*100
        r=quality.assess(b)
        self.assertEqual(r["counts"]["validated_unique_evidence_passages"],1)
        self.assertFalse(r["research_gate_passed"])

    def test_not_enough_independent_domains(self):
        b=synthetic_bundle()
        b["sources"][-1]["url"]="https://research.fao.org/report"
        r=quality.assess(b)
        self.assertEqual(r["counts"]["public_distinct_domain_groups"],4)
        self.assertFalse(r["research_gate_passed"])

    def test_no_verified_internal_action(self):
        b=synthetic_bundle()
        b["internal_actions"]=[]
        r=quality.assess(b)
        self.assertFalse(r["research_gate_passed"])
        self.assertIn("ONE_STRUCTURED_INTERNAL_RESEARCH_ACTION_REQUIRED",r["blockers"])

    def test_missing_owner_blocks_research(self):
        b=synthetic_bundle()
        b["issues"]=["MISSING_PRODUCT_OWNER"]
        self.assertFalse(quality.assess(b)["research_gate_passed"])

    def test_upstream_validation_must_pass(self):
        b=synthetic_bundle()
        b["validation_outcome"]="NEEDS_MORE_EVIDENCE"
        self.assertFalse(quality.assess(b)["research_gate_passed"])

    def test_public_https_filters_insecure_uris(self):
        for url in ["http://fao.org/report","https://127.0.0.1/","https://localhost/data",
                    "https://user:secret@fao.org/file",
                    "https://foo.invalid:444/path","https://192.168.1.1/x",
                    "https://example.com./file","https://[::1]/data"]:
            with self.subTest(url=url):
                self.assertIsNone(quality.independent_domain(url))

    def test_url_subdomains_count_as_one_independent_organization(self):
        self.assertEqual(quality.independent_domain("https://research.fao.org/x"),
                         quality.independent_domain("https://fao.org/x"))
        self.assertEqual(quality.independent_domain("https://data.gov.uk/x"),"data.gov.uk")

    def test_invalid_numeric_confidence_not_accepted(self):
        b=synthetic_bundle()
        b["evidence"][0]["confidence"]="NaN"
        self.assertEqual(quality.assess(b)["counts"]["validated_unique_evidence_passages"],99)


if __name__=="__main__":
    unittest.main()
