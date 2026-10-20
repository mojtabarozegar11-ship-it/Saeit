#!/usr/bin/env python3
"""Unified private factory inventory and real support-tool integration.

Preserves the difference between a role, a copied module, a fixture-tested tool,
a running scheduler and a native product maker. Does not start legacy robots.
"""
import argparse
import ast
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
# Installed local engines to look for; availability is not product qualification.
ENGINES={
'F01':('reportlab','zipfile'),'F02':('reportlab','zipfile'),'F03':('reportlab','zipfile'),
'F04':('docx','reportlab'),'F05':('openpyxl','reportlab'),'F06':('reportlab',),'F07':('reportlab',),
'F08':('ffmpeg',),'F09':('ffmpeg',),'F10':('reportlab',),'F11':('docx','reportlab'),
'F12':('android_sdk','gradle'),'F13':('godot',),'F14':('browser_runtime',),
'F15':('PIL','blender','ffmpeg'),'F16':('android_sdk','gradle'),'F17':('desktop_build_target',),
'F18':('http.server',),'F19':('html',),'F20':('json',),'F21':('json',),'F22':('json',),
'F23':('llama_server',),'F24':('llama_server',),'F25':('csv','json'),'F26':('torch','onnx'),
'F27':('openpyxl','libreoffice'),'F28':('math',),'F29':('docx','libreoffice'),
'F30':('pptx','libreoffice'),'F31':('reportlab',),'F32':('PIL','reportlab'),
'F33':('PIL',),'F34':('PIL',),'F35':('blender',),'F36':('blender',),
'F37':('PIL','ffmpeg'),'F38':('ffmpeg',),'F39':('ffmpeg',),'F40':('ffmpeg',)}
MODULES=('reportlab','docx','openpyxl','PIL','pptx','torch','onnx','http.server','html','json','csv','math','zipfile')
ROLES=(
 ('planning','factory_product_planner.py','individual product admission and bounded scheduling'),
 ('production','factory_40_execution_controller.py','native recipe dispatch and per-family state'),
 ('quality','factory_build_50.py','verify original manufacturing receipts and artifacts'),
 ('inventory','factory_production_warehouse.py','strict private stock admission'),
 ('delivery','factory_store_sender.py','private receipt-bound store handoff'),
 ('support_tools','factory_1000_workbench.py','offline production-support transformations'),
 ('heritage_audit','factory_legacy_77_cycle.py','isolated imported-source evaluation, not robot activation'))

def load(path,name):
    p=Path(path)
    if not p.is_file() or p.is_symlink():raise ValueError('ORGANIZER_UNTRUSTED_MODULE')
    spec=importlib.util.spec_from_file_location(name,str(p));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def hashfile(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def toolchain(ops):
    manifest=ops/'build-toolchain/toolchain-manifest.json'
    if not manifest.is_file() or manifest.is_symlink():return {'state':'unavailable','engines':{}}
    # Reuse the factory's existing version-pinned toolchain validation.
    pilot=load(HERE/'factory_specialist_pilots.py','organizer_verified_toolchain')
    try:root,python=pilot.toolchain(manifest)
    except (ValueError,RuntimeError,OSError,KeyError):return {'state':'unverified','engines':{}}
    script='import importlib.util,json; print(json.dumps({name:importlib.util.find_spec(name) is not None for name in '+repr(MODULES)+'}))'
    try:
        child=subprocess.run([str(python),'-B','-c',script],capture_output=True,text=True,timeout=15)
        if child.returncode:raise ValueError()
        engines=json.loads(child.stdout)
    except (OSError,ValueError,subprocess.TimeoutExpired):return {'state':'module_probe_failed','engines':{}}
    for name in ('ffmpeg','libreoffice','blender'):
        p=root/'bin'/name;engines[name]=p.is_file() and not p.is_symlink()
    engines['llama_server']=(root/'llama/bin/llama-server').is_file() and (root/'models/coder.gguf').is_file()
    for name in ('gradle','godot'):engines[name]=bool(shutil.which(name))
    for name in ('android_sdk','browser_runtime','desktop_build_target'):engines[name]=False
    return {'state':'version_pinned_module_and_file_probe','root_version':root.name,
      'engines':engines,'native_product_quality_inferred':False,'new_model_inference_performed':False}

def heritage(source_repo,root,planner):
    base=Path(source_repo)/'ops/factory-site-capabilities/legacy-candidates'
    origin=base/'mpw_v91_port/ORIGIN.json';rows=[]
    if origin.is_file() and not origin.is_symlink():
        data=planner.read(origin)
        for item in data.get('modules',[]):
            rel=item.get('destination','');p=base/rel
            if not isinstance(rel,str) or not rel.startswith('mpw_v91_port/legacy/') or '..' in Path(rel).parts:raise ValueError('ORGANIZER_LEGACY_PATH')
            matched=p.is_file() and not p.is_symlink() and hashfile(p)==item.get('sha256')
            rows.append({'id':rel,'source_sha256':item.get('sha256'),'source_hash_matches':matched,
              'role':'quarantined_support_candidate','production_executor_activated':False})
    receipt=root/'cross-site-capabilities/legacy-77-last-report.json';last=None
    if receipt.is_file() and not receipt.is_symlink():
        record=planner.read(receipt)
        if record.get('schema')=='saeit.factory.heritage-evaluation-cycle.v1':
            stamp=datetime.fromisoformat(record['observed_utc'].replace('Z','+00:00'))
            age=(datetime.now(timezone.utc)-stamp).total_seconds() if stamp.tzinfo else None
            last={'age_seconds':age,'fresh':age is not None and -60<=age<=7200,
              'modules_imported':record.get('real_read_only_imports'),
              'pure_function_probes':record.get('real_pure_function_probes'),
              'separate_agents_executed':record.get('separate_agents_executed')}
    robots=[]
    for filename,variable in [('mpw_main_private_execution_robots.py','ROBOTS'),('mpw_main_extended_robots.py','NAMES')]:
        path=base/'scripts'/filename
        if path.is_file() and not path.is_symlink():
            for node in ast.parse(path.read_text()).body:
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==variable for t in node.targets):
                    for name in ast.literal_eval(node.value):
                        robots.append({'role':name,'source_file_sha256':hashfile(path),'scope':'site_specific_source_only_not_factory_worker'})
    return {'robot_roles':robots,'modules':rows,'matching_modules':sum(r['source_hash_matches'] for r in rows),'last_evaluation':last,
      'copied_modules_are_product_makers':False}

def workbench(ops,root,planner):
    # Prefer the independent, receipt-verified 3000 catalog; fall back to v1.
    for version,count in ((3000,3000),(1000,1000)):
        runner=ops/('production-workbench-%d'%version)/'runner.py'
        area=root/('production-toolkit-3000' if version==3000 else 'production-toolkit')
        try:
            catalog=planner.read(area/'catalog.json');receipt=planner.read(area/'verification.json')
            if runner.is_symlink() or not runner.is_file():raise ValueError()
            if hashfile(runner)!=receipt['runtime_sha256'] or hashfile(area/'catalog.json')!=receipt['catalog_sha256']:raise ValueError()
            if len(catalog['tools'])!=count or receipt['synthetic_test_invocations_passed']!=count:raise ValueError()
            if version==3000:
                core=runner.with_name('factory_1000_workbench.py')
                if core.is_symlink() or not core.is_file() or hashfile(core)!=receipt['base_runtime_sha256']:raise ValueError()
            module=load(runner,'factory_proven_workbench_support_%d'%version)
            return module,catalog
        except (ValueError,OSError,KeyError,TypeError):
            continue
    return None,None

def run(root,registry,ops,source_repo):
    planner=load(HERE/'factory_product_planner.py','organizer_product_planner')
    master=load(HERE/'factory_40_family_master.py','organizer_family_master')
    root=Path(root);ops=Path(ops)
    if root.is_symlink() or not root.is_dir() or ops.is_symlink() or not ops.is_dir():raise ValueError('ORGANIZER_UNSAFE_ROOT')
    profiles=master.registry_valid(planner.read(registry));proto=load(HERE/'factory_build_50.py','organizer_native_receipts')
    report_path=root/'product-planning/dashboard.json'
    report=planner.read(report_path) if report_path.is_file() else {}
    if report.get('schema')!='saeit.factory.product-planning-dashboard.v1' or not 0<=time.time()-report.get('observed_unix',0)<600:
        report=planner.cycle(root,registry)
    if 'rows' not in report:raise RuntimeError('ORGANIZER_PLANNER_BUSY')
    rows=report['rows'];verified={r['family_id'] for r in rows if r['status']=='native_recipe_verified'}
    chain=toolchain(ops);wb,cat=workbench(ops,root,planner);supports=[];families=[];total=0
    for profile in profiles:
        fid=profile['id'];required=ENGINES[fid];missing=[x for x in required if not chain['engines'].get(x,False)]
        work=[]
        if wb is not None:
            calls=[(14,{'object':profile,'required':['producer_adapter','formats','specialist_tests','resource_policy']}),
             (22,{'requirements':[{'id':key,'verified':False} for key in profile['specialist_tests']]}),
             (23,{'risks':[{'name':'Native executor missing','likelihood':1 if fid in verified else 5,'impact':5}]}),
             (25,{'deliverables':profile['deliverables']}),
             (16,{'text':json.dumps(profile,sort_keys=True,ensure_ascii=False)})]
            for operation,payload in calls:
                result=wb.invoke(cat,fid+'-T%02d'%operation,payload);work.append(result);total+=1
            supports.append({'family_id':fid,'consumer':'family_engineering_readiness','real_invocations':len(work),'results':work})
        families.append({'family_id':fid,'name':profile['name_fa'],'native_executor_verified':fid in verified,
          'candidate_builder_engines':list(required),'available_candidate_engines':[x for x in required if x not in missing],
          'missing_engines':missing,'specialist_tests_required':profile['specialist_tests'],
          'readiness':'native_recipe_proven_limited_scope' if fid in verified else ('candidate_toolchain_available_requires_producer_and_qa' if not missing else 'builder_dependencies_missing'),
          'custom_product_generation_proven':False,'commercial_release':False})
    imported=heritage(source_repo,root,planner)
    role_rows=[]
    for name,filename,purpose in ROLES:
        locations=[HERE/filename,Path(source_repo)/'scripts'/filename]
        candidates=[p for p in locations if p.is_file() and not p.is_symlink()]
        role_rows.append({'role':name,'purpose':purpose,'source_available':bool(candidates),
          'source_sha256':hashfile(candidates[0]) if candidates else None,'role_definition_is_separate_agent':False})
    result={'schema':'saeit.factory.organized-capabilities.v1','observed_utc':datetime.now(timezone.utc).isoformat(),
      'family_count':40,'native_recipe_families':len(verified),'families':families,
      'candidate_engines_are_complete_builders':False,'toolchain':chain,'roles':role_rows,
      'support_tool_bindings_available':cat['tools_count'] if cat else 0,'unique_support_operations':(cat['shared_unique_operations'] if 'shared_unique_operations' in cat else len({t['operation'] for t in cat['tools']})) if cat else 0,
      'real_family_support_invocations_this_cycle':total,'family_support_receipts':supports,
      'legacy':imported,'separate_agents_started':0,'commercial_release':False,'sites_modified':False}
    area=planner.private(root/'capability-organization');planner.save(area/'dashboard.json',result)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--factory-private',required=True);p.add_argument('--registry',required=True);p.add_argument('--ops',required=True);p.add_argument('--source-repo',required=True);a=p.parse_args();r=run(a.factory_private,a.registry,a.ops,a.source_repo)
    print('FACTORY_ORGANIZED_CAPABILITIES='+json.dumps({'families':r['family_count'],'native_families':r['native_recipe_families'],'support_bindings':r['support_tool_bindings_available'],'actual_support_calls':r['real_family_support_invocations_this_cycle'],'legacy_source_hash_matches':r['legacy']['matching_modules'],'toolchain_state':r['toolchain']['state']},sort_keys=True))
