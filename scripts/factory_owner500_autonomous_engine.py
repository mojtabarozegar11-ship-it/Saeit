#!/usr/bin/env python3
"""Bounded unattended build/retest/rework loop for VERIFIED F28 factory backlog.

Selects ONE authentic owner product requirement per tick, synthesizes code from
a pinned explicit mathematical formula, runs native maker and independent ZIP
extraction tests, persists SHA-bound receipts and retries transient failures.
No arbitrary prose-to-program hallucination, AI API, payments or publication.
The existing factory's maker and QA agents are reused, not forked.
"""
import argparse
from datetime import datetime, timezone, timedelta
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile

SCHEMA="saeit.factory.autonomous-owner500-f28.v1"
FORMULAS="saeit.factory.owner-500-autonomous-formula-queue.v1"
SHA=re.compile(r"^[a-f0-9]{64}$")
ID=re.compile(r"^PD-[0-9]{4}$")
MAX_BYTES=2_000_000

def read(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("AUTONOMY_UNSAFE_OR_MISSING_SOURCE")
    raw=path.read_bytes()
    data=json.loads(raw.decode("utf8"))
    if not isinstance(data,dict):
        raise ValueError("AUTONOMY_SOURCE_OBJECT_REQUIRED")
    return raw,data

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def load(name,directory):
    path=Path(directory)/(name+".py")
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("AUTONOMY_PINNED_MODULE_REQUIRED:"+name)
    spec=importlib.util.spec_from_file_location(name+"_autonomous",path)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def atomic(path,doc,*,immutable=False):
    path=Path(path)
    if path.is_symlink() or path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError("AUTONOMY_UNSAFE_OUTPUT_PATH")
    data=(json.dumps(doc,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode("utf8")
    if path.exists():
        _,prior=read(path)
        if immutable:
            if prior!=doc:
                raise ValueError("AUTONOMY_IMMUTABLE_RECEIPT_COLLISION")
            return
    fd,tmp=tempfile.mkstemp(dir=str(path.parent),prefix=".autonomy-")
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def prepare_sources(catalog, live, formulalist):
    if (catalog.get("schema")!="saeit.factory.verified-owner-demand-portfolio.v1"
            or catalog.get("count")!=500 or catalog.get("release_authorized") is not False
            or live.get("schema")!="saeit.factory.production-instructions.v1"
            or formulalist.get("schema")!=FORMULAS
            or formulalist.get("commercial_publication_allowed") is not False):
        raise ValueError("AUTONOMY_FAIL_CLOSED_SOURCE_SCHEMA")
    products=catalog.get("products")
    live_rows=live.get("items")
    formulas=formulalist.get("formulas")
    if (not isinstance(products,list) or len(products)!=500
            or not isinstance(live_rows,list) or not 500<=len(live_rows)<=1000
            or not isinstance(formulas,list) or not 1<=len(formulas)<=50):
        raise ValueError("AUTONOMY_CATALOG_OR_QUEUE_CARDINALITY")
    by_id={p.get("id"):p for p in products if isinstance(p,dict)}
    by_live={p.get("id"):p for p in live_rows if isinstance(p,dict)}
    if len(by_id)!=500 or len(by_live)!=len(live_rows):
        raise ValueError("AUTONOMY_DUPLICATE_CATALOG_OR_SNAPSHOT")
    result=[]
    unique_ids=set()
    for item in formulas:
        if not isinstance(item,dict):
            raise ValueError("AUTONOMY_FORMULA_NOT_OBJECT")
        ident=item.get("owner_item_id")
        if (not isinstance(ident,str) or not ID.fullmatch(ident)
                or ident in unique_ids or item.get("family_id")!="F28"
                or item.get("domain_quality_approved") is not False):
            raise ValueError("AUTONOMY_FORMULA_ID_OR_CLAIM_INVALID")
        unique_ids.add(ident)
        owner=by_id.get(ident)
        live_id="factory_500_"+ident[3:]
        row=by_live.get(live_id)
        formula=item.get("definition")
        if (not isinstance(owner,dict) or owner.get("family_id")!="F28"
                or not isinstance(row,dict) or not isinstance(formula,dict)
                or owner.get("title")!=row.get("title")
                or owner.get("title")!=formula.get("title")
                or ident not in row.get("specification","")
                or not row["specification"].startswith("Family F28;")
                or owner.get("product_created") is not False
                or owner.get("quality1000_certified") is not False
                or owner.get("publication_approved") is not False):
            raise ValueError("AUTONOMY_500_ITEM_NOT_VERIFIED:"+ident)
        result.append((ident,formula,owner,row))
    return result

def run(root,catalog_file,formulas_file,scripts_dir,*,limit=1,now=None):
    root=Path(root)
    if (root.is_symlink() or not root.is_dir()
            or type(limit) is not int or not 1<=limit<=2):
        raise ValueError("AUTONOMY_UNSAFE_ROOT_OR_LIMIT")
    now=datetime.now(timezone.utc) if now is None else now
    if now.tzinfo is None:
        raise ValueError("AUTONOMY_TIMEZONE_REQUIRED")
    cat_raw,catalog=read(catalog_file)
    _,queue=read(formulas_file)
    _,live=read(root/"production-order-inputs"/"factory-invention-snapshot.json")
    selected=prepare_sources(catalog,live,queue)
    area=root/"owner500-autonomous-production"
    if area.is_symlink():
        raise RuntimeError("AUTONOMY_UNSAFE_STATE_DIRECTORY")
    area.mkdir(mode=0o700,exist_ok=True)
    histories=area/"receipts"
    if histories.is_symlink():
        raise ValueError("AUTONOMY_UNSAFE_RECEIPTS")
    histories.mkdir(mode=0o700,exist_ok=True)
    states=area/"state.json"
    lock=area/".run.lock"
    if lock.is_symlink():
        raise ValueError("AUTONOMY_LOCK_SYMLINK")
    maker=load("factory_product_maker",scripts_dir)
    intake=load("factory_design_intake",scripts_dir)
    designer=load("factory_recipe_designer",scripts_dir)
    customer=load("factory_verified_customer_cycle_20261021",scripts_dir)
    recipes=root/"generated-product-recipes"
    goods=root/"digital-products"
    if recipes.is_symlink() or not recipes.is_dir() or goods.is_symlink():
        raise RuntimeError("AUTONOMY_EXISTING_MANUFACTURING_ROOT_REQUIRED")
    goods.mkdir(mode=0o700,exist_ok=True)
    with lock.open("a+b") as lfile:
        os.fchmod(lfile.fileno(),0o600)
        fcntl.flock(lfile.fileno(),fcntl.LOCK_EX)
        if states.exists():
            _,prior=read(states)
            if prior.get("schema")!=SCHEMA or not isinstance(prior.get("items"),dict):
                raise ValueError("AUTONOMY_PREVIOUS_STATE_INVALID")
            items=dict(prior["items"])
        else:
            items={}
        events=[]
        deferred=[]
        complete=0
        for ident,formula,owner,source in selected:
            previous=items.get(ident,{})
            if not isinstance(previous,dict):
                raise ValueError("AUTONOMY_BAD_ITEM_STATE")
            artifact=previous.get("artifact_sha256")
            recipe=previous.get("recipe")
            if (previous.get("state")=="verified_private_product"
                    and isinstance(artifact,str) and SHA.fullmatch(artifact)
                    and isinstance(recipe,str) and re.fullmatch(r"synth_[a-f0-9]{24}",recipe)):
                product=goods/recipe/(recipe+"-internal-qa.zip")
                manifest=goods/recipe/"manufacturing_manifest.json"
                if (product.is_file() and not product.is_symlink() and manifest.is_file()
                        and not manifest.is_symlink() and digest(product.read_bytes())==artifact):
                    _,meta=read(manifest)
                    if meta.get("artifact_sha256")==artifact and meta.get("public_listing_enabled") is False:
                        complete+=1
                        continue
            retry_at=previous.get("retry_after_utc")
            if retry_at:
                try: due=datetime.fromisoformat(retry_at)
                except (TypeError, ValueError):
                    raise ValueError("AUTONOMY_INVALID_RETRY_TIME")
                if due>now:
                    deferred.append(ident)
                    continue
            if len(events)>=limit:
                continue
            try:
                spec=intake.expand_definition({
                    "schema":intake.SCHEMA,"family_id":"F28",
                    "mathematical_definition":formula}, "factory_invention")
                spec["upstream"]={
                    "owner_portfolio_id":ident,"owner_portfolio_sha256":digest(cat_raw),
                    "source_owner_item_sha256":designer.digest(owner),
                    "source_factory_entry_sha256":designer.digest(source),
                    "formula_sha256":designer.digest(formula),
                    "market_demand_verified":False,
                    "commercial_release":False}
                compiled=designer.compile_recipe(spec,recipes)
                recipe=compiled["recipe"]
                _,original=read(recipes/recipe/"design_request.json")
                if original!=spec:
                    raise ValueError("AUTONOMY_EQUIVALENT_BUT_DIFFERENT_SPEC")
                made=maker.manufacture(recipe,recipes,goods)
                if made.get("qa_status")!="passed":
                    raise RuntimeError("AUTONOMY_TECHNICAL_TESTS_NOT_PASSED")
                qa=customer.inspect_product(goods/recipe,recipe)
                if qa.get("customer_zip_extract_test")!="passed":
                    raise RuntimeError("AUTONOMY_INDEPENDENT_ARCHIVE_TEST_FAILED")
                customer.persist_pending(root,qa)
                receipt={
                    "schema":"saeit.factory.autonomous-owner500-receipt.v1",
                    "owner_item_id":ident,"title":owner["title"],"family_id":"F28",
                    "recipe":recipe,"artifact_sha256":qa["artifact_sha256"],
                    "source_sha256":qa["source_sha256"],"formula_sha256":designer.digest(formula),
                    "owner_catalog_sha256":digest(cat_raw),
                    "customer_independent_zip_tests":qa["customer_archive_tests_run"],
                    "independent_specialist_approval":False,
                    "quality1000_certified":False,"commercial_release":False,
                    "site_changes":0}
                receipt_file=histories/(ident+"-"+qa["artifact_sha256"][:20]+".json")
                atomic(receipt_file,receipt,immutable=True)
                next_state={
                    "state":"verified_private_product","recipe":recipe,
                    "artifact_sha256":qa["artifact_sha256"],
                    "receipt_sha256":digest(receipt_file.read_bytes()),
                    "technical_customer_qa":"passed","attempts":0,
                    "quality1000_certified":False,"publication_approved":False}
                items[ident]=next_state
                events.append({"owner_id":ident,"state":"private_product_built",
                               "created_source":compiled["created"],"new_archive":made["changed"],
                               "recipe":recipe,"customer_tests":qa["customer_archive_tests_run"],
                               "artifact_sha256":qa["artifact_sha256"]})
            except (ValueError,RuntimeError,OSError,ArithmeticError,KeyError) as error:
                tries=int(previous.get("attempts",0))+1
                cooldown=min(86400,300*(2**min(tries-1,7)))
                items[ident]={"state":"rework_required","attempts":tries,
                              "reason_code":type(error).__name__,
                              "reason":str(error)[:180],
                              "retry_after_utc":(now+timedelta(seconds=cooldown)).isoformat(),
                              "quality1000_certified":False,"publication_approved":False}
                events.append({"owner_id":ident,"state":"rework_required",
                               "attempts":tries,"reason":str(error)[:180]})
        status={
            "schema":SCHEMA,"observed_utc":now.isoformat(),"owner_backlog_total":500,
            "supported_formula_briefs":len(selected),"verified_private_products":sum(
                x.get("state")=="verified_private_product" for x in items.values()),
            "already_verified_skipped":complete,
            "new_private_products_this_tick":sum(e.get("state")=="private_product_built" and e.get("new_archive") for e in events),
            "successful_retested_products_this_tick":sum(e.get("state")=="private_product_built" for e in events),
            "rework_items_this_tick":sum(e.get("state")=="rework_required" for e in events),
            "deferred_rework":deferred,"events":events,"items":items,
            "next_action":"private_build_or_rework" if len(items)<len(selected) else "await_more_verifiable_technical_briefs",
            "unsupported_owner_needs_cannot_be_automatically_invented":500-len(selected),
            "quality1000_certified":0,"website_deployments":0,"payments_touched":0}
        atomic(states,status)
        return status

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",type=Path,required=True)
    p.add_argument("--owner-catalog",type=Path,required=True)
    p.add_argument("--formula-queue",type=Path,required=True)
    p.add_argument("--scripts-dir",type=Path,required=True)
    p.add_argument("--limit",type=int,default=1)
    a=p.parse_args()
    state=run(a.factory_private,a.owner_catalog,a.formula_queue,a.scripts_dir,limit=a.limit)
    brief={key:value for key,value in state.items() if key!="items"}
    print("FACTORY_OWNER500_AUTONOMOUS_CYCLE="+json.dumps(brief,ensure_ascii=False,sort_keys=True))
    if state["rework_items_this_tick"]:
        raise SystemExit("AUTONOMOUS_ENGINE_REWORK_CREATED_WITH_NO_FALSE_PASS")

if __name__=="__main__":
    main()
