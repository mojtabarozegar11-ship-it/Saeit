#!/usr/bin/env python3
"""Evidence-gated operational controller for ALL forty registered factory families.

This is a real scheduler controller, not a fictional 40-family product maker:
 * all 40 have concrete queue state, family-specific adapter identity & blockers
 * 3 families with genuine independently verified fifty-stage outputs remain ready
 * one original specialist pilot from 11 toolchain-supported families can execute
   per tick, never described as a completed 50-stage or saleable product
 * missing native Android, ML, CAD, authoring, mastering and legal-review tools
   are explicitly held; no invented executors, product orders or approvals
 * no action touches store sites or user financial accounts.
Stdlib only. Tested with Python 3.8+.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SCHEMA='saeit.factory.forty-family-operational-controller.v1'
PILOT_IDS=('F10','F14','F19','F27','F29','F30','F31','F33','F34','F37','F39')
FULL_PRODUCT_IDS={'F27':'capacity_planning_workbook',
                  'F19':'saas_launch_starter_2026',
                  'F34':'fieldwork_ui_48_icons',
                  'F31':'fieldwork_planner_weekly'}
KNOWN_NATIVE_ADAPTERS={'F12':'android_sdk_gradle_signed_apk_aab',
 'F13':'desktop_os_build_and_installer','F16':'android_app_signing_and_testing',
 'F17':'desktop_platform_binary_build','F26':'real_model_training_benchmark',
 'F35':'cad_export_precision_and_dimensional_review','F40':'narration_rights_and_audio_mastering',
 'F01':'subject_expert_epub_pdf','F02':'original_narrative_editor',
 'F03':'factual_citation_verifier','F04':'peer_source_research_verifier',
 'F05':'source_cited_market_data','F08':'lesson_video_editor',
 'F09':'licensed_narration_and_captions'}
def read(path, limit=2_000_000):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size>limit:
        raise ValueError('CTRL_UNTRUSTED_SOURCE')
    item=json.loads(p.read_text(encoding='utf8'))
    if not isinstance(item,dict):raise ValueError('CTRL_JSON_OBJECT_REQUIRED')
    return item

def load(name,p):
    p=Path(p)
    if not p.is_file() or p.is_symlink():raise RuntimeError('CTRL_VERIFIED_MODULE_REQUIRED')
    spec=importlib.util.spec_from_file_location(name,str(p))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def private(root):
    root=Path(root)
    if root.is_symlink():raise RuntimeError('CTRL_UNSAFE_PRIVATE_ROOT')
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not root.is_dir():raise RuntimeError('CTRL_PRIVATE_DIR_REQUIRED')
    os.chmod(root,0o700)
    return root

def plan_state(bridge,profiles,pilot_support=PILOT_IDS):
    """Reconcile each family's real technical evidence and declared adapter."""
    if bridge.get('schema')!='saeit.factory.build50-family-bridge.v1':
        raise RuntimeError('CTRL_BRIDGE_SCHEMA_MISMATCH')
    b={x['family_id']:x for x in bridge.get('families',[]) if isinstance(x,dict) and 'family_id' in x}
    if len(profiles)!=40 or len(b)!=40:
        raise RuntimeError('CTRL_NOT_ALL_FAMILIES_REGISTERED')
    rows=[]
    for entry in profiles:
        fid=entry['id']
        if fid not in b:raise RuntimeError('CTRL_FAMILY_NOT_IN_BUILD50_LEDGER')
        data=b[fid]
        confirmed=data.get('technical_50_stage_completed',0)
        pilot=data.get('technical_pilot_count',0)
        if type(confirmed) is not int or confirmed<0 or type(pilot) is not int or pilot<0:
            raise RuntimeError('CTRL_INVALID_TECHNICAL_COUNT')
        if confirmed:
            status='real_50_stage_product_exists'
            next_action='independent_human_commercial_and_legal_acceptance'
        elif fid in pilot_support and pilot:
            status='verified_technical_pilot_only'
            next_action='implement_and_independently_test_48_real_family_tasks'
        elif fid in pilot_support:
            status='queued_for_genuine_specialist_pilot'
            next_action='run_verified_private_toolchain_renderer'
        else:
            status='blocked_no_validated_native_50_stage_executor'
            next_action='implement_'+KNOWN_NATIVE_ADAPTERS.get(fid,entry['producer_adapter'])+'_and_independent_qa'
        rows.append({'family_id':fid,'slug':entry['slug'],
          'producer_adapter':entry['producer_adapter'],
          'operational_state':status,'completed_50_stage_products':confirmed,
          'verified_pilot_versions':pilot,'required_work_packages':48,
          'required_final_independent_gates':10,
          'next_action':next_action,'commercial_release_allowed':False})
    counts={'registered':len(rows),
      'families_with_real_50_stage_products':sum(x['completed_50_stage_products']>0 for x in rows),
      'families_with_verified_pilots_only':sum(x['operational_state']=='verified_technical_pilot_only' for x in rows),
      'families_with_pilot_queued':sum(x['operational_state']=='queued_for_genuine_specialist_pilot' for x in rows),
      'families_without_validated_50_stage_executor':sum(x['completed_50_stage_products']==0 for x in rows),
      'families_blocked_no_pilot_or_producer':sum(x['operational_state']=='blocked_no_validated_native_50_stage_executor' for x in rows),
      'commercially_released_products':0}
    assert sum((counts[key] for key in ('families_with_real_50_stage_products',
       'families_with_verified_pilots_only','families_with_pilot_queued',
       'families_blocked_no_pilot_or_producer')))==40
    return rows,counts

def run(root,registry,module_dir,toolchain_manifest=None,pilot=True):
    root=Path(root)
    if not root.is_dir() or root.is_symlink():raise RuntimeError('CTRL_INVALID_FACTORY_ROOT')
    module_dir=Path(module_dir)
    if not module_dir.is_dir() or module_dir.is_symlink():raise RuntimeError('CTRL_INVALID_EXECUTOR_DIR')
    ops=private(root/'production-family-management')
    if (ops/'.forty-execution.lock').is_symlink():raise RuntimeError('CTRL_SYMLINK_LOCK')
    with (ops/'.forty-execution.lock').open('a+b') as f:
        os.fchmod(f.fileno(),0o600)
        try:fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status':'another_controller_owns_lock','executed_pilot':False}
        master=load('factory_40_master_executor',module_dir/'factory_40_family_master.py')
        bridge_module=load('factory_40_evidence_executor',module_dir/'factory_build50_family_bridge.py')
        proto=load('factory_40_protocol_executor',module_dir/'factory_build_50.py')
        profiles=master.registry_valid(read(registry))
        evidence=bridge_module.inventory(root,registry,proto,master)
        rows,before=plan_state(evidence,profiles)
        executed={'status':'disabled_for_inspection','family':None,'confirmed_private_new_pilot':False}
        if pilot:
            if toolchain_manifest is None:raise RuntimeError('CTRL_TOOLCHAIN_MANIFEST_REQUIRED')
            source=module_dir/'factory_specialist_pilots.py'
            formats=module_dir/'factory_specialist_formats.py'
            if source.is_symlink() or formats.is_symlink() or not source.is_file() or not formats.is_file():
                raise RuntimeError('CTRL_SPECIALIST_EXECUTABLE_MISSING')
            pilotmod=load('factory_40_verified_pilot_executor',source)
            toolroot,python=pilotmod.toolchain(toolchain_manifest)
            if not python.is_file():raise RuntimeError('CTRL_INVALID_PINNED_TOOLCHAIN_PYTHON')
            try:
                result=subprocess.run([str(python),'-B',str(source),
                    '--out',str(root),'--manifest',str(toolchain_manifest)],
                    cwd=str(module_dir),stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    text=True,timeout=90,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',
                        OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',
                        FACTORY_TOOLCHAIN_BIN=str(toolroot/'bin')))
            except subprocess.TimeoutExpired:
                executed={'status':'pilot_failed','reason_type':'timeout',
                          'timeout_seconds':90,'confirmed_private_new_pilot':False}
            except OSError:
                executed={'status':'pilot_failed','reason_type':'launch_error',
                          'confirmed_private_new_pilot':False}
            else:
                if result.returncode:
                    executed={'status':'pilot_failed','reason_type':'nonzero_exit',
                              'exit_code':result.returncode,
                              'confirmed_private_new_pilot':False}
                else:
                    try:
                        line=next(line.split('=',1)[1] for line in result.stdout.splitlines()
                                  if line.startswith('FACTORY_SPECIALIST_PILOT='))
                        body=json.loads(line)
                        if not isinstance(body,dict):raise ValueError('invalid receipt')
                        executed={'status':body.get('status','unknown'),
                                  'family':body.get('family'),
                                  'confirmed_private_new_pilot':body.get('status')=='pilot_built'}
                    except (StopIteration,ValueError):
                        executed={'status':'pilot_receipt_not_parsable',
                                  'confirmed_private_new_pilot':False}
            # The warehouse never learns an automatic false approval from pilots.
            evidence=bridge_module.inventory(root,registry,proto,master)
            rows,after=plan_state(evidence,profiles)
        else:
            after=before
        data={'schema':SCHEMA,
              'observed_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'mode':'scheduled_private_admission_and_bounded_pilot_work',
              'registered_families':40,'families':rows,'counts':after,
              'pilot_tick_result':executed,'commercial_release_enabled':False,
              'warehouse_promotion_enabled':False,'store_publication_enabled':False,
              'customer_orders_created':0,'old_twelve_stage_governance_retained':True,
              'real_full_adapters_currently_proven':list(sorted(fid for fid in FULL_PRODUCT_IDS
                     if any(x['family_id']==fid and x['completed_50_stage_products']>0 for x in rows))),
              'warning':'Pilot artifacts and queue entries do not constitute 50-stage validated sellable products.'}
        master.atomic_json(ops/'forty-execution-dashboard.json',data)
        print('FACTORY_40_EXECUTION='+json.dumps({'counts':after,'pilot':executed},
                                                    sort_keys=True))
        return data

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--factory-private',required=True)
    parser.add_argument('--registry',required=True)
    parser.add_argument('--module-dir',required=True)
    parser.add_argument('--toolchain-manifest')
    parser.add_argument('--inspect-only',action='store_true')
    args=parser.parse_args()
    run(args.factory_private,args.registry,args.module_dir,args.toolchain_manifest,
        pilot=not args.inspect_only)
