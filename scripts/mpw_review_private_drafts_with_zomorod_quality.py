"""MojPlayWin quality reviewer adapted from current Zomorod scientific and newsroom standards.

Use original source as AST-only policy data. NEVER import/execute Zomorod modules.
Review existing MojPlayWin PRIVATE drafts, produce private decision evidence.
No publishing, money, model/network, database, Zomorod or shared Passenger.
"""
import ast, hashlib, json, os, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

REFERENCE=Path("/home/zomorod2/.private_mojplaywin_main_agents/zomorod_django_agent_sources_20261018")
STATE=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018/operator_state")
INPUT_LIMIT=48000
MAX_DOCS=300

def check(cond,message):
    if not cond:raise RuntimeError(message)
def private_dir(path):
    return path.is_dir() and not path.is_symlink() and (path.stat().st_mode&0o077)==0
def policy_from_source(root):
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf8"))
    def get(rel,vars):
        path=root/"reference"/rel
        data=path.read_bytes()
        check(path.is_file() and not path.is_symlink(),"UNSAFE_SOURCE")
        check(hashlib.sha256(data).hexdigest()==manifest["files"][rel],"SOURCE_HASH_INVALID")
        tree=ast.parse(data.decode("utf-8"))
        out={}
        for node in tree.body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                name=node.targets[0].id
                if name in vars:
                    try:out[name]=ast.literal_eval(node.value)
                    except (ValueError,TypeError,SyntaxError):pass
        return out
    knowledge=get("core/knowledge_quality.py",("QUALITY_GATES","SEO_REQUIREMENTS"))
    newsroom=get("core/newsletter_engine.py",("MIN_AUTO_PUBLISH_SCORE",))
    gates=knowledge.get("QUALITY_GATES")
    seo=knowledge.get("SEO_REQUIREMENTS")
    threshold=newsroom.get("MIN_AUTO_PUBLISH_SCORE")
    check(isinstance(gates,(list,tuple)) and "source_provenance" in gates and "publication_control" in gates,"QUALITY_GATES_MISSING")
    check(isinstance(seo,(list,tuple)) and len(seo)>=5,"SEO_POLICY_MISSING")
    check(isinstance(threshold,int) and 50<=threshold<=100,"NEWSROOM_THRESHOLD_MISSING")
    return {"quality_gates":list(gates),"seo_requirements":list(seo),
            "source_newsroom_threshold":threshold,
            "references_sha256":{k:manifest["files"][k] for k in
                ("core/knowledge_quality.py","core/newsletter_engine.py")}}

def assess(payload,policy):
    draft=payload.get("draft",{})
    title=draft.get("title","") if isinstance(draft,dict) else ""
    summary=draft.get("summary","") if isinstance(draft,dict) else ""
    body=draft.get("body","") if isinstance(draft,dict) else ""
    sources=draft.get("sources",[]) if isinstance(draft,dict) else []
    if not isinstance(title,str):title=""
    if not isinstance(summary,str):summary=""
    if not isinstance(body,str):body=""
    if not isinstance(sources,list):sources=[]
    valid_refs=[]
    for item in sources[:12]:
        if not isinstance(item,str) or len(item)>400:continue
        try:
            p=urlsplit(item)
            if p.scheme=="https" and p.hostname and not p.username and not p.password:
                valid_refs.append(item)
        except ValueError:pass
    facts={
        "tenant_valid":isinstance(draft,dict) and draft.get("tenant")=="mojplaywin-main",
        "review_only":isinstance(draft,dict) and draft.get("review_required") is True
                    and draft.get("published") is False,
        "title_readable":35<=len(title)<=220,
        "summary_substantial":len(summary)>=180,
        "body_substantial":len(body)>=1200,
        "reference_https":len(valid_refs)>0,
        "body_has_evidence_cues":any(z in body for z in ("منبع","شواهد","روش","تحلیل","داده","study","evidence")),
        "uncertainty_disclosed":any(z in body for z in ("محدودیت","عدم قطعیت","احتمال","ممکن است","uncertainty","limitations")),
        "seo_headings":any(z in body for z in ("\n#", "\n##", "عنوان", "heading")),
    }
    # A high editorial score is not factual validation or authorization to publish.
    weights={"title_readable":10,"summary_substantial":14,"body_substantial":23,
             "reference_https":18,"body_has_evidence_cues":12,
             "uncertainty_disclosed":12,"seo_headings":11}
    score=sum(v for k,v in weights.items() if facts[k])
    return {"quality_score":score,"checks":facts,
            "quality_release_threshold":policy["source_newsroom_threshold"],
            "status":"review_ready_not_published" if score>=policy["source_newsroom_threshold"]
                and facts["tenant_valid"] and facts["review_only"] else "needs_editorial_revision",
            "policy_gates_count":len(policy["quality_gates"]),
            "seo_requirements_count":len(policy["seo_requirements"]),
            "never_auto_publish":True}

def safe_json(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>INPUT_LIMIT:return None
    try:
        row=json.loads(path.read_text(encoding="utf8"))
        return row if isinstance(row,dict) else None
    except (OSError,UnicodeError,ValueError):return None
def atomic_report(path,content):
    content=json.dumps(content,ensure_ascii=False,sort_keys=True).encode()
    fd,temp=tempfile.mkstemp(prefix=".tmp-mpw-review-",dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as h:
            h.write(content);h.flush();os.fsync(h.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def review_private(state=STATE,ref=REFERENCE):
    check(private_dir(state) and private_dir(ref),"PRIVATE_SOURCE_OR_STATE_INVALID")
    check(private_dir(state/"processed") and private_dir(state/"drafts"),"INPUTS_MISSING")
    policy=policy_from_source(ref)
    review_dir=state/"quality_reviews"
    if review_dir.is_symlink():raise RuntimeError("UNSAFE_REVIEW_DIR")
    review_dir.mkdir(mode=0o700,exist_ok=True)
    check(private_dir(review_dir),"QUALITY_REVIEWS_DIR_NOT_PRIVATE")
    examined=0
    tallies={"review_ready_not_published":0,"needs_editorial_revision":0}
    for original in sorted((state/"processed").glob("*.json"))[:MAX_DOCS]:
        if original.is_symlink() or not original.is_file() or original.stat().st_size>INPUT_LIMIT:continue
        raw=original.read_bytes()
        key=hashlib.sha256(raw).hexdigest()[:24]
        request=safe_json(original)
        source=safe_json(state/"drafts"/(key+".json"))
        if not isinstance(request,dict) or request.get("tenant")!="mojplaywin-main" or request.get("review_only") is not True:
            continue
        if not isinstance(source,dict) or not isinstance(source.get("draft"),dict):
            continue
        result=assess(source,policy)
        if not result["checks"]["tenant_valid"] or not result["checks"]["review_only"]:
            continue
        out=review_dir/(key+".json")
        evidence={"tenant":"mojplaywin-main","source_task_digest":key,
                  "reviewed_utc":datetime.now(timezone.utc).isoformat(),
                  "kind":request.get("kind"),**result}
        atomic_report(out,evidence)
        examined+=1
        tallies[result["status"]]+=1
    return {"status":"MPW_ZOMOROD_QUALITY_STANDARDS_USED_IN_PRIVATE_REVIEW",
            "actual_private_drafts_scored":examined,
            "quality_review_results":tallies,
            "knowledge_quality_gates":len(policy["quality_gates"]),
            "seo_requirements":len(policy["seo_requirements"]),
            "original_newsroom_threshold":policy["source_newsroom_threshold"],
            "source_hashes_verified":True,
            "website_published":False,"factory_or_zomorod_modified":False}

if __name__=="__main__":
    print(json.dumps(review_private(),ensure_ascii=False,sort_keys=True))
