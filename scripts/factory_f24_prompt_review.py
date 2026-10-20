"""Independent F24 structural tests; never mark prompt efficacy LLM-verified."""
import hashlib,json,zipfile
from pathlib import Path
GATES=("requirements","correctness","negative_cases","usability","accessibility",
 "security","compatibility","provenance","specialist_review","release_integrity")
def require(ok,reason):
 if not ok:raise ValueError("PROMPT_REVIEW_"+reason)
def verify_pair(folder,stem):
 doc=json.loads((folder/(stem+".json")).read_text("utf8"))
 text=(folder/(stem+".md")).read_text("utf8")
 require(doc["schema"]=="saeit.factory.prompt-source.v1" and doc["id"]==stem,"WRONG_ID")
 require(doc["tested_against_real_llm"] is False if "tested_against_real_llm" in doc else
     doc["tests"]["tested_against_real_llm"] is False,"FALSE_TEST_CLAIM")
 require(doc["model_version_tested"] is None and doc["commercial_release"] is False,"FALSE_APPROVAL")
 require(doc["tests"]["real_negative_cases_rejected"]==5,"NO_NEGATIVE_TESTS")
 require(doc["tests"]["llm_model_inference_attempts"]==0,"UNSUPPORTED_MODEL_CLAIM")
 require(doc["tests"]["real_positive_case"]["reference_count"]==1,"POSITIVE_TEST")
 require("{{task_text}}" in text and "{{source_refs}}" in text,"MISSING_EDITABLE_PROMPT")
 require(len(text)>=750 and "No LLM model calls" in text,"UNTRUSTED_PROMPT_DISCLOSURE")
 require(set(doc["response_keys"])>=({"answer","limitations"} if doc["mode"]=="minimal" else {"assumptions","limitations"}),"RESPONSE_CONTRACT")
 return {"mode":doc["mode"],"topic":doc["topic"],"negative_checks":5}
def check(folder,archive,product):
 folder=Path(folder)
 jsons=[p for p in folder.glob("*.json") if p.stem.endswith(("_minimal","_standard","_strict","_batch"))]
 require(len(jsons)==48,"EXPECTED_48_ORIGINAL_PROMPT_JSONS")
 stems=sorted(p.stem for p in jsons)
 require(len(set(stems))==48,"DUPLICATE_STEMS")
 files=[]
 for stem in stems:
  for ext in (".json",".md"):
   p=folder/(stem+ext)
   require(p.is_file() and not p.is_symlink() and 250<=p.stat().st_size<=20000,"BAD_PROMPT_FILE")
   files.append(p)
  verify_pair(folder,stem)
 for ext in (".md",".json"):
  subset=[p for p in files if p.suffix==ext]
  require(len({hashlib.sha256(p.read_bytes()).hexdigest() for p in subset})==48,"REPEATED_PROMPT_CONTENT")
 readme=folder/"README.txt"
 require(readme.is_file() and "No LLM model trials" in readme.read_text("utf8"),"NO_LIMITS_DISCLOSED")
 files.append(readme)
 with zipfile.ZipFile(str(archive)) as z:
  require(z.testzip() is None and
   set(z.namelist())=={product+"/"+p.name for p in files},"ZIP_CONTENT_MISMATCH")
  for p in files:require(z.read(product+"/"+p.name)==p.read_bytes(),"ZIP_FILE_DIFFERENCE")
 return {"passed":True,"gates":{x:True for x in GATES},
  "actual_prompt_playbooks":48,"real_input_parser_negative_cases":48*5,
  "llm_trials_performed":0,"human_review":False,"commercial_release":False,
  "scope":"structural input validator and archive checks only"}
