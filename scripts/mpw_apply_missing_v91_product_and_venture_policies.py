"""Apply seven verified V91 scientific/commercial policies to MojPlayWin PRIVATE drafts.

Uses original V91 pure-library policies only; no Django or payment flows,
no fake prices, sale authorizations, claims of market data or public output.
"""
import hashlib,importlib,json,os,sys,tempfile
from pathlib import Path
from datetime import datetime,timezone
PARENT=Path("/home/zomorod2/.private_mojplaywin_main_agents")
POLICIES=PARENT/"v91_missing_safe_policy_modules_20261018"
STATE=PARENT/"v91_verified_main_port_20261018/operator_state"
MAX_DRAFTS=120
MAX_DOCUMENT=50000

def require(cond,reason):
    if not cond:raise RuntimeError(reason)

def private_dir(path):
    return path.is_dir() and not path.is_symlink() and path.stat().st_mode&0o077==0

def data(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>MAX_DOCUMENT:
        return None
    try:
        val=json.loads(path.read_bytes())
        return val if isinstance(val,dict) else None
    except (ValueError,OSError,UnicodeError):
        return None

def atomic_json(path,obj):
    raw=json.dumps(obj,ensure_ascii=False,sort_keys=True).encode("utf8")
    fd,tmp=tempfile.mkstemp(prefix=".tmp-mpw-policy-",dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def build_adjudicator(policy_dir):
    require(private_dir(policy_dir),"POLICY_MODULE_STAGE_MISSING")
    manifest=data(policy_dir/"manifest.json")
    require(manifest is not None and manifest.get("tenant")=="mojplaywin-main","INVALID_MANIFEST")
    modules=manifest.get("files",{})
    require(len(modules)==7,"INCOMPLETE_SOURCE_POLICIES")
    for rel,properties in modules.items():
        p=policy_dir/rel
        require(p.is_file() and not p.is_symlink(),"SOURCE_NOT_PRESENT")
        require(hashlib.sha256(p.read_bytes()).hexdigest()==properties["sha256"],"SOURCE_HASH_CHANGED")
    # Use source code directly, not rewritten versions, inside the separate verified namespace.
    sys.path.insert(0,str(policy_dir))
    from portal import autopilot_rules,commercial_quality,venture_engine,workbook_generator
    from portal import editorial_review_v26,title_match,site_cycle_budget
    return (autopilot_rules,commercial_quality,venture_engine,workbook_generator,
            editorial_review_v26,title_match,site_cycle_budget)

def audit_one(req,source,qreview,policies):
    rules,commercial,venture,workbook,editorial,title,budget=policies
    kind=req.get("kind","research_digest")
    draft=source.get("draft")
    require(isinstance(draft,dict),"INVALID_DRAFT")
    name=draft.get("title","")
    body=draft.get("body","")
    sources=draft.get("sources",[])
    category="digital" if kind=="product_blueprint" else "research"
    good,reason=rules.reusable_content_ok(body,name,category,sources)
    quality_score=qreview.get("quality_score") if isinstance(qreview,dict) else None
    quality_approval=(isinstance(qreview,dict) and
                      qreview.get("status")=="review_ready_not_published"
                      and isinstance(quality_score,int) and quality_score>=90)
    human_evidence=req.get("commercial_evidence") if isinstance(req.get("commercial_evidence"),dict) else {}
    validated,commercial_reason=commercial.review_valid(human_evidence)
    scores=req.get("venture_scores")
    venture_result={"status":"no_explicit_owner_ratings"}
    keys=[key for key,_,_ in venture.DIMENSIONS]
    if isinstance(scores,dict) and set(scores)==set(keys):
        try:
            rating,_=venture.score(scores)
            venture_result={"status":"owner_supplied_scenario_only",
                            "score":rating,"claimed_market_revenue":False}
        except (venture.InputError,TypeError,ValueError):
            venture_result={"status":"invalid_supplied_ratings"}
    questions=editorial.domain_evidence({"title":category}) if isinstance(name,str) else {}
    tokens=sorted(title.normalized_tokens(name))[:15]
    # Not enough approved material to make an asset for sale. Never create
    # a paid workbook without a human-reviewed and sourced original article.
    workbook_gate={
        "allowed":bool(quality_approval and good and validated and req.get("approved_source_for_workbook") is True),
        "candidate_source_passes_reuse_policy":good,
        "source_policy_reason":reason,
        "quality_reviewer_passed":quality_approval,
        "human_commercial_review_passed":validated,
        "human_review_reason":commercial_reason,
        "offline_workbook_created":False,
    }
    return {
        "tenant":"mojplaywin-main","kind":kind,"title_tokens":tokens,
        "policy_evidence_question":questions.get("source_rule",""),
        "policy_quality":"eligible_for_owner_review" if good else "blocked_needs_review",
        "commercial_value_review":commercial_reason,
        "venture_screen":venture_result,
        "workbook_gate":workbook_gate,
        "sale_ready":False,"auto_publish":False,"payment_enabled":False,
    }

def run_audit(root=STATE,stage=POLICIES):
    require(private_dir(root),"PRIVATE_STATE_UNAVAILABLE")
    require(private_dir(root/"processed") and private_dir(root/"drafts"),"DRAFTS_NOT_AVAILABLE")
    libs=build_adjudicator(stage)
    outcome=root/"v91_product_policy_audits"
    if outcome.is_symlink():raise RuntimeError("POLICY_DEST_SYMLINK")
    outcome.mkdir(mode=0o700,exist_ok=True)
    require(private_dir(outcome),"POLICY_DEST_NOT_PRIVATE")
    inspected=0
    blocked=0
    with_human_review=0
    budget=libs[-1].CycleBudget(seconds=60)
    for f in sorted((root/"processed").glob("*.json"))[:MAX_DRAFTS]:
        if budget.expired():break
        if f.is_symlink() or not f.is_file() or f.stat().st_size>MAX_DOCUMENT:continue
        request=data(f)
        sha=hashlib.sha256(f.read_bytes()).hexdigest()[:24]
        product=data(root/"drafts"/(sha+".json"))
        quality=data(root/"quality_reviews"/(sha+".json"))
        if not request or not product or request.get("tenant")!="mojplaywin-main" or request.get("review_only") is not True:
            continue
        original=product.get("draft")
        if not isinstance(original,dict) or original.get("tenant")!="mojplaywin-main" or original.get("published") is not False:
            continue
        findings=audit_one(request,product,quality,libs)
        atomic_json(outcome/(sha+".json"),{
            "reviewed_utc":datetime.now(timezone.utc).isoformat(),
            "task_digest":sha,**findings})
        inspected+=1
        blocked+=int(not findings["workbook_gate"]["allowed"])
        with_human_review+=int(findings["workbook_gate"]["human_commercial_review_passed"])
    return {"status":"MPW_V91_MISSING_POLICY_ENGINES_APPLIED_REAL_DRAFTS",
            "verified_original_engines":7,"real_drafts_screened":inspected,
            "workbooks_blocked_pending_real_approval":blocked,
            "commercial_human_evidence_passed":with_human_review,
            "site_modified":False,"zomorod_site_modified":False,
            "factory_modified":False,"auto_publish":False,"money_collected":False}

if __name__=="__main__":
    print(json.dumps(run_audit(),sort_keys=True,ensure_ascii=False))
