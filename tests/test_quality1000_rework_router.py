"""Regression: only real 100x10 receipts route; no forged 1000 or sale."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from factory_quality_1000_v2 import grade, CRITERIA
from quality1000_evidence_gate import inspect
from quality1000_rework_router import route, ticket

class RouteQualityTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.base=self.root/"quality-excellence"
        self.order_folder=self.base/"production-workorders"/"test_recipe"
        self.quality_folder=self.base/"rework"/"test_recipe"
        self.order_folder.mkdir(parents=True)
        self.quality_folder.mkdir(parents=True)

    def assessment(self, valid_one=False, forged=False):
        evidence={}
        if valid_one:
            data=self.root/"measured.txt"
            data.write_bytes(b"independent documentary hash check only " * 3)
            evidence["Q001"]={"path":"measured.txt","sha256":hashlib.sha256(data.read_bytes()).hexdigest()}
        report={"family_id":"F14","blockers":[]}
        card=grade(report,exact_build_sha256="a"*64,criteria_evidence=evidence,evidence_root=self.root)
        if forged:
            card["professional_quality_1000_passed"]=True
        assessment={"schema":"saeit.factory.quality-rework.v2",
            "recipe":"test_recipe","family_id":"F14","artifact_sha256":"a"*64,
            "quality_1000_scorecard":card,"quality_group_count":100,
            "quality_points_per_group":10,"required_quality_points":1000,
            "quality_points_verified":None,"defects":[],
            "commercial_release_allowed":False,"premium_quality_approved":False}
        raw=(json.dumps(assessment,sort_keys=True)+"\n").encode()
        missing=[q for q in CRITERIA if card["criteria"][q]["documentary_points"]!=10]
        order={"schema":"saeit.factory.production-rework-order.v1",
            "recipe":"test_recipe","artifact_sha256":"a"*64,
            "source_quality_receipt_sha256":hashlib.sha256(raw).hexdigest(),
            "required_criterion_work":[{"group_id":i} for i in missing],
            "unresolved_technical_or_domain_defects":[],
            "commercial_publish_allowed":False,
            "signed_external_quality_approval_required":True,
            "owner_release_approval_required":True}
        (self.quality_folder/"current.json").write_bytes(raw)
        (self.order_folder/"current.json").write_text(json.dumps(order)+"\n")
        return assessment,raw,order

    def test_real_one_hundred_groups_route_and_immutable_dedup(self):
        self.assessment()
        result=route(self.root)
        self.assertEqual(result["routed_products"],1)
        self.assertEqual(result["queued_issues"],100)
        self.assertEqual(result["professional_quality_certifications"],0)
        self.assertEqual(result["sites_modified"],0)
        saved=self.base/"specialist-routed-rework"/"test_recipe"
        receipt=next(saved.glob("route-*.json"))
        task=json.loads(receipt.read_text())
        self.assertEqual(len(task["tasks"]),100)
        self.assertFalse(task["publication_allowed"])
        self.assertFalse(task["quality_1000_certified"])
        self.assertFalse(task["master_task_dispatch_verified"])
        self.assertEqual(task["producer_module"],"factory_six_specialist_executors.py")
        again=route(self.root)
        self.assertEqual(result["receipts"],again["receipts"])
        self.assertEqual(len(list(saved.glob("route-*.json"))),1)

    def test_real_documentary_evidence_reduces_work_not_certification(self):
        self.assessment(valid_one=True)
        result=route(self.root)
        self.assertEqual(result["queued_issues"],99)
        saved=self.base/"specialist-routed-rework"/"test_recipe"/"current.json"
        route_row=json.loads(saved.read_text())
        self.assertEqual(route_row["documentary_points"],10)
        self.assertEqual(route_row["certified_quality_points"],None)
        self.assertFalse(route_row["publication_allowed"])

    def test_assessment_hash_and_artifact_binding_required(self):
        a,raw,o=self.assessment()
        o["source_quality_receipt_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"SOURCE_ORDER_NOT_BOUND"):
            ticket(a,raw,o)
        o["source_quality_receipt_sha256"]=hashlib.sha256(raw).hexdigest()
        o["artifact_sha256"]="b"*64
        with self.assertRaisesRegex(ValueError,"SOURCE_ORDER_NOT_BOUND"):
            ticket(a,raw,o)

    def test_forged_quality_approval_is_rejected(self):
        a,raw,o=self.assessment(forged=True)
        with self.assertRaisesRegex(RuntimeError,"INVALID_1000_QUALITY_SCORE"):
            inspect(a,raw,o)

    def test_partial_workorder_or_wrong_criterion_fails(self):
        a,raw,o=self.assessment()
        o["required_criterion_work"].pop()
        with self.assertRaisesRegex(ValueError,"CRITERIA_MISMATCH"):
            ticket(a,raw,o)

    def test_input_symlink_is_not_routed(self):
        self.assessment()
        p=self.order_folder/"current.json"
        real=self.order_folder/"real.json"
        p.rename(real)
        p.symlink_to(real)
        result=route(self.root)
        self.assertEqual(result["routed_products"],0)
        self.assertEqual(len(result["rejected_products"]),1)

    def test_legacy_ten_group_scorecard_cannot_claim_1000(self):
        a,raw,o=self.assessment()
        a["quality_1000_scorecard"]={"schema":"saeit.quality1000.v1",
                                     "criteria":{"functionality":{"score":100}}}
        with self.assertRaisesRegex(RuntimeError,"INVALID_1000_QUALITY_SCORE"):
            inspect(a,raw,o)


    def test_legacy_edition_quarantine_is_actionable_not_certified(self):
        assessment={"schema":"saeit.factory.quality-rework.v2",
                    "recipe":"test_recipe","quality_status":"QUARANTINE_AUDIT_ERROR",
                    "defects":["P0_AUDIT_ERROR_ValueError"],
                    "quality_points_verified":None,"premium_quality_approved":False,
                    "commercial_release_allowed":False}
        raw=(json.dumps(assessment,sort_keys=True)+"\n").encode()
        order={"schema":"saeit.factory.production-rework-order.v1",
               "recipe":"test_recipe","artifact_sha256":None,
               "source_quality_receipt_sha256":hashlib.sha256(raw).hexdigest(),
               "commercial_publish_allowed":False,"owner_release_approval_required":True,
               "signed_external_quality_approval_required":True,
               "unresolved_technical_or_domain_defects":["P0_AUDIT_ERROR_ValueError"]}
        (self.quality_folder/"current.json").write_bytes(raw)
        (self.order_folder/"current.json").write_text(json.dumps(order))
        result=route(self.root)
        self.assertEqual(result["routed_products"],1)
        self.assertEqual(result["queued_issues"],1)
        entry=json.loads((self.base/"specialist-routed-rework"/"test_recipe"/"current.json").read_text())
        self.assertEqual(entry["disposition"],"QUARANTINED_NEEDS_ORIGINAL_SOURCE")
        self.assertIsNone(entry["artifact_sha256"])
        self.assertIsNone(entry["documentary_points"])
        self.assertFalse(entry["quality_1000_certified"])


    def test_missing_family_is_quarantined_not_assigned_fake_agent(self):
        self.assessment()
        source=self.quality_folder/"current.json"
        assessment=json.loads(source.read_text())
        assessment["family_id"]=None
        raw=(json.dumps(assessment,sort_keys=True)+"\n").encode()
        source.write_bytes(raw)
        orderfile=self.order_folder/"current.json"
        order=json.loads(orderfile.read_text())
        order["source_quality_receipt_sha256"]=hashlib.sha256(raw).hexdigest()
        orderfile.write_text(json.dumps(order))
        report=route(self.root)
        self.assertEqual(report["routed_products"],1)
        latest=json.loads((self.base/"specialist-routed-rework"/"test_recipe"/"current.json").read_text())
        self.assertEqual(latest["disposition"],"QUARANTINED_UNMAPPED_FAMILY")
        self.assertIsNone(latest["producer_module"])
        self.assertFalse(latest["publication_allowed"])

if __name__=="__main__":
    unittest.main()
