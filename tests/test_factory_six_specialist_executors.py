"""Regression suite against six REAL private worker artifacts, not fake 50-stage stock."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"factory_six_specialist_executors.py"
spec=importlib.util.spec_from_file_location("six_worker_under_test",str(SCRIPT))
agent=importlib.util.module_from_spec(spec);spec.loader.exec_module(agent)

class SixWorkerRegression(unittest.TestCase):
    def setUp(self):
        context=tempfile.TemporaryDirectory()
        self.addCleanup(context.cleanup)
        self.root=Path(context.name)

    def test_exact_six_and_real_private_product_bytes(self):
        result=agent.run(self.root,all_six=True)
        self.assertEqual(result["registered_workers"],list(agent.FAMILIES))
        self.assertEqual(len(result["outcomes"]),6)
        self.assertEqual(result["technical_candidates_rechecked"],6)
        self.assertEqual(result["native_50_stage_executors_certified"],0)
        self.assertEqual(result["independent_quality_1000_certified"],0)
        self.assertFalse(result["public_release_authorized"])
        self.assertEqual(result["sites_modified"],0)
        for item in result["outcomes"]:
            self.assertTrue(item["agent_executed"],item)
            self.assertTrue(item["technical_candidate_hash_verified"],item)
            self.assertFalse(item["commercial_release"])
            self.assertFalse(item["quality_1000_certified"])
            self.assertTrue(item["archive_sha256"])
        second=agent.run(self.root,all_six=True)
        self.assertEqual(second["technical_candidates_rechecked"],6)
        self.assertEqual({x["family"]:x["archive_sha256"] for x in result["outcomes"]},
                         {x["family"]:x["archive_sha256"] for x in second["outcomes"]})

    def test_five_fail_closed_on_source_tamper(self):
        builder=agent.load("factory_seven_missing_builders.py","test_producer")
        reply=builder.create(self.root,"F17")
        product="fieldwork_desktop_inventory_software_pilot"
        folder=(self.root/"engineering-gaps"/"seven-builders"/product/
                reply["private_archive_sha256"][:20]/product)
        (folder/"desktop.py").write_text("tampered\n",encoding="utf8")
        with self.assertRaisesRegex(RuntimeError,"SIX_PRODUCT_SOURCE_HASH_MISMATCH"):
            agent.verify_five(self.root,"F17",reply)

    def test_reject_fake_independent_approval(self):
        builder=agent.load("factory_seven_missing_builders.py","test_rejection_producer")
        reply=builder.create(self.root,"F12")
        folder=(self.root/"engineering-gaps"/"seven-builders"/
                "fieldwork_mobile_puzzle_game_pilot"/reply["private_archive_sha256"][:20])
        p=folder/"technical_receipt.json"
        record=json.loads(p.read_text())
        record["independent_quality_1000_passed"]=True
        p.write_text(json.dumps(record))
        with self.assertRaisesRegex(RuntimeError,"SIX_BUILDER_RECEIPT_CONTRACT_INVALID"):
            agent.verify_five(self.root,"F12",reply)

    def test_broken_one_family_does_not_hide_failures(self):
        original=agent.execute
        def partial(root,fid):
            if fid=="F14":raise RuntimeError("missing browser builder")
            return original(root,fid)
        with patch.object(agent,"execute",side_effect=partial):
            result=agent.run(self.root,all_six=True)
        self.assertEqual(result["technical_candidates_rechecked"],5)
        issue=next(x for x in result["outcomes"] if x["family"]=="F14")
        self.assertFalse(issue["agent_executed"])
        self.assertFalse(issue["technical_candidate_hash_verified"])
        self.assertFalse(result["public_release_authorized"])

    def test_one_worker_per_tick_with_persisted_rotation(self):
        observed=[]
        for i in range(6):
            outcome=agent.run(self.root)
            observed.append(outcome["selected"][0])
            self.assertEqual(outcome["technical_candidates_rechecked"],1)
        self.assertEqual(observed,list(agent.FAMILIES))

if __name__=="__main__":
    unittest.main()
