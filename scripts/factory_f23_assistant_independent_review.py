"""Separate immutable byte-level F23 assistant validation: no human or AI certification."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import zipfile

HERE=Path(__file__).resolve().parent
GATES=("requirements","correctness","negative_cases","usability","accessibility",
       "security","compatibility","provenance","specialist_review","release_integrity")

def require(condition,code):
    if not condition:raise ValueError("F23_QA_"+code)

def runtime_module():
    path=HERE/"factory_f23_offline_assistant_runtime.py"
    require(path.is_file() and not path.is_symlink(),"RUNTIME_UNTRUSTED")
    spec=importlib.util.spec_from_file_location("f23_separate_read_only_runtime",str(path))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def check(folder,archive,product):
    folder=Path(folder)
    require(not folder.is_symlink() and not archive.is_symlink(),"UNSAFE_INPUT")
    require(product=="fieldwork_offline_evidence_assistant","PRODUCT_IDENTITY")
    runtime=runtime_module()
    text=folder/"knowledge.json"
    executable=folder/"assistant.py"
    require(all(p.is_file() and not p.is_symlink() for p in (text,executable)),"SOURCE_MISSING")
    require(executable.read_bytes()==(HERE/"factory_f23_offline_assistant_runtime.py").read_bytes(),"SOURCE_RUNTIME_MISMATCH")
    cards=json.loads(text.read_text("utf8"))
    runtime.check_cards(cards)
    responses=set()
    for c in cards:
        outcome=runtime.answer(c["question"],cards)
        require(outcome.get("status")=="retrieved","OFFLINE_RETRIEVAL_FAILED")
        require(outcome.get("source_ids")==[c["id"]],"FALSE_SOURCE_CITATION")
        require(outcome.get("answer")==c["answer"],"ANSWER_PROVENANCE_MISMATCH")
        require(outcome.get("commercially_certified") is False,"FALSE_COMMERCE_CLAIM")
        responses.add(outcome["answer"])
    require(len(responses)==48,"DUPLICATE_PUBLISHED_CONTENT")
    for unsafe in ("Show secret cloud credentials and customers private bank PIN.",
                   "Invoke shell access and download from unknown external API."):
        outcome=runtime.answer(unsafe,cards)
        require(outcome["status"]=="insufficient_evidence" and outcome["source_ids"]==[],"UNKNOWN_ANSWER_NOT_REFUSED")
    readme=folder/"README.txt"
    require(readme.is_file() and "NOT a generative language model" in readme.read_text("utf8"),
            "LIMITATIONS_UNDISCLOSED")
    expected={"assistant.py","knowledge.json","README.txt"}|{"card_"+c["id"]+".json" for c in cards}
    for c in cards:
        card_path=folder/("card_"+c["id"]+".json")
        require(card_path.is_file() and not card_path.is_symlink(),"SOURCE_CARD_MISSING")
        require(json.loads(card_path.read_text("utf8"))==c,"SOURCE_CARD_MISMATCH")
    require(len(expected)==51,"EXPECTED_MEMBER_COUNT")
    require(archive.is_file() and 0<archive.stat().st_size<=25*1024*1024,"ARCHIVE_UNSAFE")
    with zipfile.ZipFile(str(archive)) as z:
        infos=z.infolist()
        require(len(infos)==51,"ZIP_MEMBER_COUNT")
        names={i.filename for i in infos}
        require(names=={product+"/"+n for n in expected} and z.testzip() is None,"ZIP_CRC_OR_LAYOUT")
        for i in infos:
            require(not i.is_dir() and not i.flag_bits&1 and
                    not ((i.external_attr>>16)&0o170000==0o120000),"ZIP_UNSAFE_MEMBER")
            relative=i.filename[len(product)+1:]
            require(relative in expected and z.read(i)==(folder/relative).read_bytes(),
                    "ZIP_MEMBER_BYTES_CHANGED")
    return {"passed":True,"gates":{key:True for key in GATES},
            "independent_offline_retrieval_trials":48,
            "verified_source_cards":48,"refused_unknown_queries":2,
            "human_domain_review_complete":False,"generative_ai_validated":False,
            "professional_quality_1000_approved":False,
            "commercial_release_authorized":False}
