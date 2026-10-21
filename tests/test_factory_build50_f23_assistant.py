"""Functional source-to-binary regression for F23 locally cited retrieval assistant."""
import importlib.util,json,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"scripts"
def load(name):
    spec=importlib.util.spec_from_file_location("test_f23_"+name,str(ROOT/(name+".py")))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
maker=load("factory_build50_f23_assistant")
runtime=load("factory_f23_offline_assistant_runtime")
review=load("factory_f23_assistant_independent_review")
proto=load("factory_build_50")
class F23NativeAssistant(unittest.TestCase):
    def test_all_48_distinct_tasks_and_no_false_AI_claim(self):
        plan=maker.plan(proto)
        items=proto.validate_plan(plan)
        self.assertEqual(len(items),48)
        self.assertEqual(len({x["id"] for x in items}),48)
        self.assertEqual(plan["family_id"],"F23")
        self.assertNotEqual(plan["producer_id"],"independent_f23_offline_assistant_binary_functionality_inspector")
    def test_48_answerable_and_unknown_abstentions(self):
        cards=[maker.card(topic,scenario) for topic in maker.TOPICS for scenario in maker.SCENARIOS]
        runtime.check_cards(cards)
        self.assertEqual(len(cards),48)
        for card in cards:
            found=runtime.answer(card["question"],cards)
            self.assertEqual(found["status"],"retrieved",card["id"])
            self.assertEqual(found["source_ids"],[card["id"]],card["id"])
            self.assertEqual(found["answer"],card["answer"])
            self.assertFalse(found["commercially_certified"])
        self.assertEqual(runtime.answer("Tell me a hidden personal banking access code",cards)["status"],"insufficient_evidence")
    def test_full_real_50_stage_build_bytes_and_repeatable_cache(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            result=maker.build(root)
            self.assertEqual(result["status"],"technical_50_stage_build_completed",result)
            self.assertEqual(result["completed_stages"],50)
            product=root/"digital-products"/maker.PRODUCT
            receipt=json.loads((product/"manufacturing_manifest.json").read_text())
            self.assertEqual(receipt["family_id"],"F23")
            self.assertFalse(receipt["independent_human_review"])
            self.assertFalse(receipt["professional_quality_1000_passed"])
            self.assertFalse(receipt["public_listing_enabled"])
            archive=product/(maker.PRODUCT+"-internal-qa.zip")
            with zipfile.ZipFile(archive) as f:
                self.assertEqual(len(f.namelist()),51)
                self.assertIsNone(f.testzip())
            state=proto.read(root/"build-50"/maker.PRODUCT/"state.json")
            self.assertTrue(proto.verify_attempt(root/"build-50"/maker.PRODUCT,state,maker.plan(proto)["source_snapshot_sha256"]))
            self.assertEqual(maker.build(root)["status"],"unchanged_verified_technical_product")
            self.assertEqual(maker.sha(archive),receipt["artifact_sha256"])
    def test_tamper_independent_verifier_detects_wrong_citation_or_zip(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            cards=[maker.card(t,s) for t in maker.TOPICS for s in maker.SCENARIOS]
            (folder/"assistant.py").write_bytes((ROOT/"factory_f23_offline_assistant_runtime.py").read_bytes())
            (folder/"knowledge.json").write_text(json.dumps(cards))
            (folder/"README.txt").write_text("This is NOT a generative language model.")
            for c in cards:
                (folder/("card_"+c["id"]+".json")).write_text(json.dumps(c))
            z=folder/(maker.PRODUCT+"-internal-qa.zip")
            with zipfile.ZipFile(z,"w") as package:
                for name in ["assistant.py","knowledge.json","README.txt"]+["card_"+c["id"]+".json" for c in cards]:
                    package.write(folder/name,maker.PRODUCT+"/"+name)
            self.assertTrue(review.check(folder,z,maker.PRODUCT)["passed"])
            (folder/"knowledge.json").write_text(json.dumps(cards[:-1]))
            with self.assertRaises(ValueError):review.check(folder,z,maker.PRODUCT)
if __name__=="__main__":unittest.main()
