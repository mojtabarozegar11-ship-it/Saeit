import importlib.util,tempfile,unittest,json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]/"scripts"
def load(n):
 sp=importlib.util.spec_from_file_location(n,str(BASE/(n+".py")))
 m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
builder=load("factory_build50_f24_prompts")
review=load("factory_f24_prompt_review")
proto=load("factory_build_50")
class PromptProduct(unittest.TestCase):
 def test_48_distinct_work_packages(self):
  tasks=proto.validate_plan(builder.plan(proto))
  self.assertEqual(len(tasks),48)
  self.assertEqual(len({x["id"] for x in tasks}),48)
 def test_real_machine_positive_and_negative_cases(self):
  data=builder.tests("draft_email","minimal")
  self.assertEqual(data["real_negative_cases_rejected"],5)
  self.assertEqual(data["llm_model_inference_attempts"],0)
 def test_producer_evidence_not_model_trials(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);task=builder.plan(proto)["work_packages"][0]
   builder.produce(p,task)
   result=review.verify_pair(p,task["id"])
   self.assertEqual(result["negative_checks"],5)
   name=p/(task["id"]+".json")
   doc=json.loads(name.read_text())
   doc["tests"]["llm_model_inference_attempts"]=9
   name.write_text(json.dumps(doc))
   with self.assertRaisesRegex(ValueError,"UNSUPPORTED_MODEL_CLAIM"):
    review.verify_pair(p,task["id"])
if __name__=="__main__":unittest.main()
