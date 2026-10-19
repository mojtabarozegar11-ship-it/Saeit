#!/usr/bin/env python3
"""40-family routing bridge for the installed 1+48+1 manufacturing protocol.

Never turns a technical pilot or a green unit test into owner/commerce approval.
An honest snapshot, not a simulated execution: each family's genuine
BUILD50 state is reverified from all 50 receipts and immutable source/ZIP.
No sales, order generation, web calls, source deletion, or worker invention.
Python 3.8+, stdlib only.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent
DASHBOARD='saeit.factory.build50-family-bridge.v1'
HASH=re.compile(r'^[0-9a-f]{64}$')
ID=re.compile(r'^[A-Za-z][A-Za-z0-9_-]{1,90}$')

def module(name,filename):
    path=HERE/filename
    if not path.is_file() or path.is_symlink():raise RuntimeError('BRIDGE_MODULE_INVALID:'+filename)
    spec=importlib.util.spec_from_file_location(name,str(path))
    instance=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instance)
    return instance

def read(path,limit=2_000_000):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>limit:
        raise ValueError('BRIDGE_UNTRUSTED_JSON')
    item=json.loads(path.read_text(encoding='utf8'))
    if not isinstance(item,dict):raise ValueError('BRIDGE_JSON_OBJECT_REQUIRED')
    return item

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(65536),b''):h.update(chunk)
    return h.hexdigest()

def safe_parent(root,path):
    path=Path(path)
    if path.is_symlink():return False
    try:path.resolve().relative_to(root.resolve())
    except ValueError:return False
    return True

def one(root,name,proto,registered):
    folder=root/'build-50'/name
    state_file=folder/'state.json'
    if not safe_parent(root,folder) or not safe_parent(root,state_file):
        return {'status':'untrusted_attempt_path','verified':False}
    if not state_file.is_file():
        return {'status':'awaiting_50_stage_executor','verified':False}
    try:
        state=read(state_file)
    except (ValueError,OSError):
        return {'status':'invalid_stage_state','verified':False}
    stages=state.get('completed_stages')
    if type(stages) is not int or stages<0 or stages>50:stages=0
    if state.get('status')!='awaiting_owner_acceptance' or stages!=50:
        return {'status':'rework_required' if state.get('status')=='rework_required' else 'incomplete',
                'verified':False,'completed_stages':stages}
    attempt=folder/'attempt-%08d'%state.get('attempt',-1) if type(state.get('attempt')) is int else folder/'INVALID'
    if not safe_parent(root,attempt) or not attempt.is_dir():
        return {'status':'invalid_attempt_directory','verified':False}
    try:
        plan=read(attempt/'01-plan.json')
        family=plan.get('family_id')
        if family not in registered:
            return {'status':'missing_registered_family_binding','verified':False,'completed_stages':stages}
        snapshot=state.get('source_snapshot_sha256')
        if not isinstance(snapshot,str) or not HASH.fullmatch(snapshot):
            return {'status':'invalid_source_snapshot','verified':False,'completed_stages':stages}
        if not proto.verify_attempt(folder,state,snapshot):
            return {'status':'corrupt_50_stage_proof','verified':False,'completed_stages':stages,'family_id':family}
        return {'status':'50_stage_technical_proof_verified','verified':True,
                'completed_stages':50,'family_id':family,'owner_acceptance_pending':True}
    except (ValueError,OSError,KeyError,RuntimeError,TypeError):
        return {'status':'invalid_50_stage_proof','verified':False,'completed_stages':stages}

def inventory(root,registry,proto,master):
    base=Path(root)
    if base.is_symlink() or not base.is_dir():raise RuntimeError('BRIDGE_PRIVATE_ROOT_INVALID')
    registry_file=Path(registry)
    profiles=master.registry_valid(read(registry_file))
    by_family={p['id']:p for p in profiles}
    families={fid:{'family_id':fid,'family_slug':p['slug'],'required_stages':50,
      'worker_packages_required':48,'technical_50_stage_completed':0,
      'commercially_released':0,'technical_pilot_count':0,
      '50_stage_attempts_requiring_rework':0,
      'executor_status':'verified_50_stage_executor_available' if fid=='F27' else 'family_executor_not_yet_verified',
      'next_action':'verify_specialist_producer_and_48_distinct_work_packages' if fid!='F27' else 'owner_and_independent_commercial_acceptance'}
      for fid,p in by_family.items()}
    products=[]
    base50=base/'build-50'
    if base50.is_symlink():raise RuntimeError('BRIDGE_UNSAFE_BUILD50_PATH')
    if base50.exists():
        for folder in sorted(base50.iterdir()):
            if folder.is_symlink() or not folder.is_dir() or not ID.fullmatch(folder.name):
                continue
            entry=one(base,folder.name,proto,by_family)
            entry['product_id']=folder.name
            products.append(entry)
            fid=entry.get('family_id')
            if fid in families:
                if entry.get('verified'):
                    families[fid]['technical_50_stage_completed']+=1
                elif entry.get('status')=='rework_required':
                    families[fid]['50_stage_attempts_requiring_rework']+=1
    for fid,p in by_family.items():
        pilot=base/'family-pilots'/fid
        if pilot.is_symlink():raise RuntimeError('BRIDGE_UNSAFE_PILOT_DIR')
        if not pilot.is_dir():continue
        for version in pilot.iterdir():
            if version.is_symlink() or not version.is_dir() or not re.fullmatch('[0-9a-f]{20}',version.name):
                continue
            source=version/'technical-receipt.json'
            try:
                obj=read(source,200_000)
                members=obj.get('files')
                valid=(obj.get('family')==fid and obj.get('source_key')==version.name
                    and obj.get('technical_quality_passed') is True and obj.get('commercial_release') is False
                    and isinstance(members,dict) and len(members)>0)
                for filename,expected in members.items() if isinstance(members,dict) else []:
                    f=version/filename
                    if (not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',filename)
                        or not isinstance(expected,str) or not HASH.fullmatch(expected)
                        or not safe_parent(base,f) or not f.is_file() or digest(f)!=expected):
                        valid=False;break
                if valid:families[fid]['technical_pilot_count']+=1
            except (OSError,ValueError,TypeError,KeyError):
                continue
    stock=base/'production-warehouse'/'stock-register.json'
    warehouse={'verified_build50_stocked':0,'technical_versions_awaiting_commercial_review':0}
    if stock.is_file() and not stock.is_symlink():
        register=read(stock)
        warehouse['technical_versions_awaiting_commercial_review']=register.get('awaiting_commercial_review',0)
        for record in register.get('records',[]):
            if not isinstance(record,dict):continue
            candidate=record.get('product_id')
            if candidate in (p['product_id'] for p in products if p.get('verified')):
                warehouse['verified_build50_stocked']+=1
    counts={'registered_families':len(families),
            'families_with_valid_50_stage_technical_proof':sum(x['technical_50_stage_completed']>0 for x in families.values()),
            'technical_products_with_verified_50_stages':sum(x.get('verified',False) for x in products),
            'families_without_verified_50_stage_executor':sum(x['executor_status']=='family_executor_not_yet_verified' for x in families.values()),
            'families_with_private_technical_pilots':sum(x['technical_pilot_count']>0 for x in families.values()),
            'commercially_approved_and_published_products':0}
    if counts['registered_families']!=40:raise RuntimeError('BRIDGE_EXPECTED_40_FAMILIES')
    return {'schema':DASHBOARD,'observed_utc':datetime.now(timezone.utc).isoformat(),
       'build50_protocol':'1_planning_48_distinct_worker_packages_1_independent_final_review',
       'source':'read_existing_private_factory_state_only',
       'commercial_release_allowed':False,'payment_or_orders_created':False,
       'sites_contacted':0,'existing_12_stage_governance_unchanged':True,
       'family_executor_contract':'Must produce 48 non-reused real artifacts, independent reviewer evidence and pass all 10 mandatory quality gates',
       'counts':counts,'families':list(families.values()),'products':products,
       'warehouse':warehouse}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--factory-private',required=True)
    ap.add_argument('--registry',required=True)
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    root=Path(args.factory_private)
    output=Path(args.output)
    if output.is_symlink() or output.parent.is_symlink() or not safe_parent(root,output):
        raise RuntimeError('BRIDGE_OUTPUT_OUTSIDE_PRIVATE_FACTORY')
    proto=module('factory_build50_bridge_protocol','factory_build_50.py')
    master=module('factory_forty_bridge_registry','factory_40_family_master.py')
    result=inventory(root,args.registry,proto,master)
    master.private_dir(output.parent)
    master.atomic_json(output,result)
    print('FACTORY_BUILD50_FAMILY_BRIDGE='+json.dumps(result['counts'],sort_keys=True))
    print('FACTORY_BUILD50_STOCK_LIFECYCLE=technical_only_awaiting_owner')

if __name__=='__main__':main()
