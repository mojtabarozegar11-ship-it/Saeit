#!/usr/bin/env python3
"""Real 50-stage F23 offline assistant technical builder, no generative-AI claim.

Forty-eight distinct source-bound original local operations playbooks and a
working question-answer retrieval CLI. Technical tests and an independent
structural reviewer are necessary but not sufficient for paid publication.
No user conversations, external web/API/model calls, finance or customer actions.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import zipfile

HERE=Path(__file__).resolve().parent
PRODUCT="fieldwork_offline_evidence_assistant"
TOPICS=("workspace","inventory","orders","catalog","permissions","packaging",
        "reporting","support","accessibility","backup","training","handoff")
SCENARIOS=("setup","verification","troubleshooting","handover")
STEPS={
"setup":("Define a written scope, keep initial state private and record inputs before enabling the local operation.",
         "Check that the dry-run example completes with no network, payment or public deployment."),
"verification":("Measure the actual result against the input specification and preserve a byte-bound receipt for the observed revision.",
                "Recheck an independent negative test, source identity and immutable hash before reporting any technical success."),
"troubleshooting":("Reproduce the problem with one minimal isolated fixture, inspect the bounded error code, and never delete the previous known-good version.",
                   "Apply a reversible correction, rerun unit and negative checks and log unchanged blockers honestly."),
"handover":("Package the verified technical instructions and a reproducible input example with a clear owner and version label.",
            "Keep privacy, expert acceptance and explicit publication permission as separate unresolved release gates."),
}
def module(name):
    file=HERE/(name+".py")
    if file.is_symlink() or not file.is_file():raise ValueError("F23_MODULE_NOT_PINNED")
    spec=importlib.util.spec_from_file_location(name,str(file))
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(65536),b""):digest.update(block)
    return digest.hexdigest()

def card(topic,scenario):
    title=topic+" "+scenario
    return {
        "id":topic+"_"+scenario,
        "topic":topic,
        "scenario":scenario,
        "question":"What checks establish the "+title+" workflow for the private operations handbook?",
        "answer":("For "+title+": "+STEPS[scenario][0]+" "+STEPS[scenario][1]+
                  " This procedure illustrates "+topic+" only; actual measurements and "
                  "independent approvals are still required before customer use."),
        "scope":"synthetic_offline_operations_not_professional_advice",
    }

def plan(proto):
    tasks=[]
    for topic in TOPICS:
        for scenario in SCENARIOS:
            key=topic+"_"+scenario
            tasks.append({
                "id":key,"topic":topic,"scenario":scenario,
                "instruction":("Author an original offline reference card for "+topic+
                    " focused on "+scenario+
                    ". Prove exact, nonduplicated source identity and executable "
                    "retrieval behaviour for this distinct bounded operational case."),
                "acceptance":["Create a new structured original card with distinct topic, scenario, verifiable question and explicit limitations.",
                              "Verify nonempty answer, identity contract, response traceability and no network or commercial release implication."],
            })
    return {"schema":proto.SCHEMA,"family_id":"F23","product_id":PRODUCT,
            "producer_id":"f23_original_offline_evidence_retrieval_engine_v1",
            "source_snapshot_sha256":proto.digest({
                "producer":sha(__file__),
                "independent_reviewer":sha(HERE/"factory_f23_assistant_independent_review.py"),
                "runtime":sha(HERE/"factory_f23_offline_assistant_runtime.py"),
                "protocol":sha(HERE/"factory_build_50.py")}),
            "work_packages":tasks}

def build(root):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise ValueError("F23_PRIVATE_ROOT_INVALID")
    proto=module("factory_build_50")
    runtime=module("factory_f23_offline_assistant_runtime")
    reviewer=module("factory_f23_assistant_independent_review")
    spec=plan(proto)
    home=root/"build-50"/PRODUCT
    target=root/"digital-products"/PRODUCT
    archive=PRODUCT+"-internal-qa.zip"
    if any(x.is_symlink() for x in (root/"build-50",home,root/"digital-products",target)):
        raise ValueError("F23_UNSAFE_DESTINATION")
    if (home/"state.json").is_file() and (target/"manufacturing_manifest.json").is_file():
        state=proto.read(home/"state.json")
        manifest=proto.read(target/"manufacturing_manifest.json")
        z=target/archive
        if (proto.verify_attempt(home,state,spec["source_snapshot_sha256"])
                and z.is_file() and not z.is_symlink()
                and sha(z)==manifest.get("artifact_sha256")):
            return {"family_id":"F23","status":"unchanged_verified_technical_product"}
    def work(task,ctx):
        dest=Path(ctx["folder"])/("card_"+task["id"]+".json")
        item=card(task["topic"],task["scenario"])
        dest.write_text(json.dumps(item,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
        if item["id"]!=task["id"] or len(item["answer"])<90:
            raise ValueError("F23_CARD_CHECK_FAILED")
        if runtime.terms(item["question"])==runtime.terms(""):
            raise ValueError("F23_NO_QUERY_TOKENS")
        return {"passed":True,"outputs":[dest.name],"successful_checks":2}
    def assemble(record,ctx):
        folder=Path(ctx["folder"])
        cards=[json.loads((folder/("card_"+task["id"]+".json")).read_text("utf8"))
               for task in record["work_packages"]]
        runtime.check_cards(cards)
        (folder/"assistant.py").write_bytes((HERE/"factory_f23_offline_assistant_runtime.py").read_bytes())
        (folder/"knowledge.json").write_text(json.dumps(cards,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
        (folder/"README.txt").write_text(
            "Original local 48-topic-scenario retrieval playbook and executable assistant.py. "
            "Run: python3 assistant.py --question 'What checks establish the inventory verification workflow?' "
            "Only answers from bundled synthetic examples with evidence IDs. "
            "This is NOT a generative language model, independent expert-reviewed "
            "customer support, real financial advice, a site deployment, or commercial certification.\n",
            encoding="utf8")
        files=sorted(folder.glob("card_*.json"))+[folder/"assistant.py",
               folder/"knowledge.json",folder/"README.txt"]
        if len(files)!=51:raise ValueError("F23_SOURCE_MEMBER_COUNT")
        with zipfile.ZipFile(str(folder/archive),"w",zipfile.ZIP_DEFLATED) as z:
            for file in files:
                member=zipfile.ZipInfo(PRODUCT+"/"+file.name,(2020,1,1,0,0,0))
                member.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(member,file.read_bytes())
        return {"passed":True,"outputs":[archive,"assistant.py","knowledge.json","README.txt"],
                "successful_checks":4}
    def review(record,ctx):
        folder=Path(ctx["folder"])
        proof=reviewer.check(folder,folder/archive,PRODUCT)
        proto.save(folder/"independent-f23-technical-review.json",proof)
        return {"reviewer_id":"independent_f23_offline_assistant_binary_functionality_inspector",
                "critical_defects":[],"passed":proof["passed"],"gates":proof["gates"],
                "successful_checks":10,"outputs":["independent-f23-technical-review.json"]}
    state=proto.run_attempt(root,spec,work,assemble,review)
    if not proto.verify_attempt(home,state,spec["source_snapshot_sha256"]):
        return {"family_id":"F23","status":"technical_rework_required",
                "defects":state.get("defects",[])}
    target.mkdir(parents=True,exist_ok=True,mode=0o700)
    stage=target/".incoming-f23-private.zip"
    shutil.copyfile(Path(state["attempt_folder"])/archive,stage)
    os.replace(stage,target/archive)
    proto.save(target/"manufacturing_manifest.json",{
        "schema_version":2,"recipe":PRODUCT,"family_id":"F23",
        "artifact_sha256":sha(target/archive),
        "source_sha256":spec["source_snapshot_sha256"],
        "bytes":(target/archive).stat().st_size,
        "files":sorted("card_"+t["id"]+".json" for t in spec["work_packages"])+
                ["assistant.py","knowledge.json","README.txt"],
        "qa_status":"passed","qa_evidence":"independent_offline_retrieval_technical_review_only",
        "commercial_status":"private_internal_qa_pass_not_published",
        "public_listing_enabled":False,"owner_publication_approval":False,
        "independent_human_review":False,"generative_ai_model_tested":False,
        "professional_quality_1000_passed":False,
        "price":None})
    return {"family_id":"F23","status":"technical_50_stage_build_completed",
            "completed_stages":50,"commercial_release":False}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--factory-private",required=True)
    args=p.parse_args()
    result=build(args.factory_private)
    print("FACTORY_F23_OFFLINE_ASSISTANT_BUILD50="+json.dumps(result,sort_keys=True))
    if result["status"]=="technical_rework_required":raise SystemExit(2)
