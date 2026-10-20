#!/usr/bin/env python3
"""Per-product planning and honest bounded dispatch for all forty families.

Custom objectives never silently resolve to a fixed catalog kit. Plans are not
production receipts. Unimplemented specialist executors remain explicit blockers.
"""
import argparse
from collections import Counter
from datetime import date,timedelta
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE=Path(__file__).resolve().parent
SCHEMA='saeit.factory.product-request.v1'
CATALOG={'F18':'fieldwork_local_calculator_webapps','F19':'saas_launch_starter_2026','F20':'fieldwork_validation_plugins','F21':'fieldwork_developer_text_tools',
 'F22':'fieldwork_record_workflows','F25':'fieldwork_synthetic_edge_fixtures','F27':'capacity_planning_workbook',
 'F28':'fieldwork_engineering_calculators','F34':'fieldwork_ui_48_icons'}
BATCH={'F20','F21','F22','F25','F28'}

def load(name):
    p=HERE/(name+'.py')
    if p.is_symlink() or not p.is_file():raise ValueError('PLANNER_UNSAFE_MODULE')
    spec=importlib.util.spec_from_file_location(name,str(p));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def private(p):
    p=Path(p)
    if p.is_symlink():raise ValueError('PLANNER_UNSAFE_DIRECTORY')
    p.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(p,0o700)
    return p

def read(p):
    p=Path(p)
    if p.is_symlink() or not p.is_file() or p.stat().st_size>2_000_000:raise ValueError('PLANNER_UNSAFE_INPUT')
    v=json.loads(p.read_text('utf8'))
    if not isinstance(v,dict):raise ValueError('PLANNER_OBJECT_REQUIRED')
    return v

def save(p,v):
    if p.is_symlink():raise ValueError('PLANNER_UNSAFE_OUTPUT')
    raw=json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)
    if p.is_file() and p.read_text('utf8')==raw:return
    fd,tmp=tempfile.mkstemp(dir=str(p.parent),prefix='.plan-')
    try:
        with os.fdopen(fd,'w',encoding='utf8') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def request(value,profiles):
    if not isinstance(value,dict):raise ValueError('PLANNER_OBJECT_REQUIRED')
    if value.get('schema')!=SCHEMA or value.get('family_id') not in profiles:raise ValueError('PLANNER_REQUEST_SCHEMA')
    family=value['family_id'];kind=value.get('kind')
    if kind not in ('catalog','custom','qualification'):raise ValueError('PLANNER_REQUEST_KIND')
    if kind=='catalog':
        if set(value)-{'schema','family_id','kind','recipe','parameters'}:raise ValueError('PLANNER_CATALOG_CANNOT_ACCEPT_CUSTOM_OBJECTIVES')
        parameters=value.get('parameters',{})
        if not isinstance(parameters,dict):raise ValueError('PLANNER_PARAMETERS_OBJECT')
        if family=='F31':
            if value.get('recipe')!='weekly_planner' or set(parameters)!={'week'}:raise ValueError('PLANNER_WEEK_REQUIRED')
            week=date.fromisoformat(parameters['week'])
            if week.weekday()!=0:raise ValueError('PLANNER_WEEK_MUST_BE_MONDAY')
            product='fieldwork_planner_'+week.strftime('%Y%m%d')
        else:
            if family not in CATALOG or value.get('recipe')!=CATALOG[family] or parameters:raise ValueError('PLANNER_UNKNOWN_CATALOG_SCOPE')
            product=CATALOG[family]
        return dict(value,parameters=parameters,product_id=product)
    objective=value.get('objective');requirements=value.get('requirements')
    if not isinstance(objective,str) or not 10<=len(objective.strip())<=2000:raise ValueError('PLANNER_OBJECTIVE_REQUIRED')
    if (not isinstance(requirements,list) or not 2<=len(requirements)<=48
        or any(not isinstance(x,str) or not 10<=len(x.strip())<=2000 for x in requirements)
        or len(set(requirements))!=len(requirements)):raise ValueError('PLANNER_DISTINCT_REQUIREMENTS_REQUIRED')
    units=value.get('components',[])
    if not isinstance(units,list) or len(units)>8 or any(not isinstance(x,str) or not 3<=len(x)<=160 for x in units) or len(set(units))!=len(units):raise ValueError('PLANNER_COMPONENTS_INVALID')
    for field in ('audience','language'):
        if not isinstance(value.get(field),str) or not 2<=len(value[field])<=160:raise ValueError('PLANNER_AUDIENCE_AND_LANGUAGE_REQUIRED')
    evidence=value.get('evidence',[])
    if not isinstance(evidence,list) or len(evidence)>40:raise ValueError('PLANNER_EVIDENCE_INVALID')
    allowed={'schema','family_id','kind','objective','requirements','components','audience','language','evidence'}
    if set(value)-allowed:raise ValueError('PLANNER_UNKNOWN_REQUEST_FIELD')
    return {k:value[k] for k in sorted(value)}

def evidence_checks(root,refs):
    valid=[];invalid=[]
    for ref in refs:
        try:
            if not isinstance(ref,dict) or set(ref)!={'path','sha256','purpose'}:raise ValueError()
            name=ref['path'];purpose=ref['purpose'];expected=ref['sha256']
            if not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts or '\\' in name:raise ValueError()
            p=root/name;p.resolve().relative_to(root.resolve())
            if any(parent.is_symlink() for parent in (p,*p.parents) if parent!=root.parent):raise ValueError()
            if not isinstance(purpose,str) or not 3<=len(purpose)<=100 or not re.fullmatch('[a-f0-9]{64}',str(expected)):raise ValueError()
            if not p.is_file() or p.stat().st_size>8_000_000 or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError()
            valid.append(purpose)
        except (ValueError,OSError,TypeError):invalid.append('invalid_or_unverified_evidence')
    return set(valid),invalid

def prepare(root,req,profile,routes):
    family=req['family_id'];units=req.get('components') or list(routes.ROUTES[family])
    # Preserve eight substantive family-specific units when fewer custom units exist.
    units=units+[x for x in routes.ROUTES[family] if x not in units]
    units=units[:8];requirements=req.get('requirements') or list(profile['specialist_tests'])
    tasks=[]
    for i,unit in enumerate(units):
        for phase,verb in routes.PHASES:
            tasks.append({'id':'component_'+chr(97+i)+'_'+phase,'component':unit,'phase':phase,
              'instruction':verb+' '+unit+' for '+req.get('objective',req.get('product_id','family qualification'))+'. Check '+requirements[i%len(requirements)]+'.',
              'acceptance':['Output fulfills the named requirement with a source-bound artifact.',
                            'Record actual independent test evidence; a plan or success flag is insufficient.'],
              'status':'not_executed','evidence':[]})
    verified,invalid=evidence_checks(root,req.get('evidence',[]))
    missing=[] if req['kind']=='catalog' else [x for x in routes.INPUTS[family] if x not in verified]
    blockers=list(invalid)
    if req['kind']!='catalog':blockers+=['validated_custom_product_executor_missing']+['input:'+x for x in missing]
    return {'schema':'saeit.factory.per-product-plan.v1','request_sha256':digest(req),'family_id':family,
      'request':req,'objective':req.get('objective',req.get('product_id')),
      'work_packages':tasks,'planning_is_manufacturing':False,'planned_work_packages':48,
      'completed_planned_work_packages':0,'formats':profile['formats'],'specialist_tests':profile['specialist_tests'],
      'resource_policy':profile['resource_policy'],'missing_inputs':missing,'blockers':blockers,
      'executor_scope':'fixed_catalog_recipe_only' if req['kind']=='catalog' else 'custom_engineering_not_implemented',
      'requires_independent_manufacturing_plan':True,'commercial_release':False}

def proof(root,product,family,proto):
    try:
        home=root/'build-50'/product
        if home.is_symlink() or (root/'build-50').is_symlink():return None
        state=read(home/'state.json');snapshot=state['source_snapshot_sha256']
        if not proto.verify_attempt(home,state,snapshot):return None
        actual=read(Path(state['attempt_folder'])/'01-plan.json')
        if actual.get('family_id')!=family or actual.get('product_id')!=product:return None
        manifest=read(root/'digital-products'/product/'manufacturing_manifest.json');archive=root/'digital-products'/product/(product+'-internal-qa.zip')
        if archive.is_symlink() or archive.parent.is_symlink() or not archive.is_file() or archive.stat().st_size>25_000_000:return None
        archive_hash=hashlib.sha256(archive.read_bytes()).hexdigest()
        final=read(Path(state['attempt_folder'])/'50-summary.json')
        if (manifest.get('family_id')!=family or manifest.get('recipe')!=product
            or manifest.get('qa_status')!='passed' or archive_hash!=manifest.get('artifact_sha256')
            or archive_hash not in final.get('outputs',{}).values()):return None
        return {'product_id':product,'family_id':family,'source_snapshot_sha256':snapshot,
          'native_build_plan_sha256':proto.digest(actual),'verified_manufacturing_receipts':50,
          'native_work_packages':len(actual['work_packages']),'custom_requirements_satisfied':False}
    except (OSError,ValueError,KeyError,TypeError):return None

def resources(root):
    available=None
    try:
        line=next(x for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
        available=int(line.split()[1])//1024
    except (OSError,StopIteration,ValueError):pass
    try:load=os.getloadavg()[0]
    except OSError:load=None
    return {'memory_available_mb':available,'disk_free_mb':shutil.disk_usage(root).free//1048576,
      'cpu_count':os.cpu_count() or 1,'load_average':load}

def admissible(capacity):
    reasons=[]
    if capacity['memory_available_mb'] is None or capacity['memory_available_mb']<384:reasons.append('memory_below_safe_reserve')
    if capacity['disk_free_mb']<2048:reasons.append('disk_below_safe_reserve')
    if capacity['load_average'] is not None and capacity['load_average']>capacity['cpu_count']*2:reasons.append('cpu_busy')
    return reasons

def command_for(root,req):
    family=req['family_id'];timeout=90
    if family in BATCH:command=[sys.executable,'-B',str(HERE/'factory_batch5_build.py'),'--family',family,'--factory-private',str(root)]
    elif family in ('F18','F19'):
        script={'F18':'factory_build50_f18_webapps.py','F19':'factory_build50_f19_web_template.py'}[family]
        command=[sys.executable,'-B',str(HERE/script),'--factory-private',str(root)]
    elif family=='F31':command=[sys.executable,'-B',str(HERE/'factory_build50_f31_planner.py'),'--factory-private',str(root),'--week',req['parameters']['week']]
    elif family in ('F27','F34'):
        manifest=Path(root).parent.parent/'operations/build-toolchain/toolchain-manifest.json'
        _,python=load('factory_specialist_pilots').toolchain(manifest)
        script={'F27':'factory_build50_workbook.py','F34':'factory_build50_f34_icon_kit.py'}[family]
        command=[str(python),'-B',str(HERE/script),'--factory-private',str(root)]
        if family=='F27':command+=['--toolchain',str(manifest),'--worker'];timeout=210
    else:raise ValueError('PLANNER_EXECUTOR_NOT_ROUTED')
    return command,timeout

def execute(root,req):
    try:command,timeout=command_for(root,req)
    except (ValueError,RuntimeError,OSError,KeyError):
        return {'status':'blocked_executor_or_toolchain_unavailable','retry_after_seconds':3600}
    # Kill the whole child process group on timeout; leave evidence for safe retry.
    child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True,
      env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
    try:
        out,err=child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL);child.communicate()
        return {'status':'timed_out','retry_after_seconds':300}
    return {'status':'execution_returned' if child.returncode==0 else 'execution_failed','exit_code':child.returncode,
      'retry_after_seconds':300,'output_sha256':hashlib.sha256(out.encode()).hexdigest()}

def seeds(profiles):
    today=date.today();week=(today-timedelta(days=today.weekday())).isoformat();rows=[]
    for family,p in profiles.items():
        base={'schema':SCHEMA,'family_id':family}
        if family in CATALOG:rows.append(dict(base,kind='catalog',recipe=CATALOG[family]))
        elif family=='F31':rows.append(dict(base,kind='catalog',recipe='weekly_planner',parameters={'week':week}))
        else:rows.append(dict(base,kind='qualification',objective='Qualify a genuine specialist producer for '+p['slug'],
          requirements=['Produce the declared editable and usable deliverables.','Pass independent '+', '.join(p['specialist_tests'])+' tests.'],audience='internal engineering',language='en'))
    return rows

def cycle(root,registry,dispatch=False,max_execute=1):
    root=Path(root)
    if not root.is_dir() or root.is_symlink():raise ValueError('PLANNER_ROOT_REQUIRED')
    if type(max_execute) is not int or not 0<=max_execute<=2:raise ValueError('PLANNER_EXECUTION_LIMIT')
    area=private(root/'product-planning');intake=private(area/'intake');plans=private(area/'plans');states=private(area/'states')
    lock=area/'.planner.lock'
    if lock.is_symlink():raise ValueError('PLANNER_LOCK_SYMLINK')
    with lock.open('a+b') as handle:
        os.fchmod(handle.fileno(),0o600)
        try:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'status':'already_running'}
        master=load('factory_40_family_master');proto=load('factory_build_50');routes=load('factory_product_routes')
        profiles={p['id']:p for p in master.registry_valid(read(registry))}
        if set(routes.ROUTES)!=set(profiles) or set(routes.INPUTS)!=set(profiles):raise ValueError('PLANNER_ALL_FORTY_ROUTES_REQUIRED')
        files=sorted(intake.iterdir())
        if len(files)>500:raise ValueError('PLANNER_INTAKE_CAPACITY_EXCEEDED')
        raw=seeds(profiles);rejected=[];legacy_aliases={};legacy_scanned=0
        old=root/'production-instructions'/'orders'
        if old.exists():
            if old.is_symlink():raise ValueError('PLANNER_LEGACY_ORDER_SYMLINK')
            existing=sorted(old.glob('WO-*.json'))
            if len(existing)>15000:raise ValueError('PLANNER_LEGACY_ORDER_CAPACITY')
            for path in existing:
                try:
                    item=read(path);legacy_scanned+=1
                    if item.get('phase')!='engineering_specification' or item.get('family_id') not in profiles:continue
                    if item.get('status') in ('completed_verified','in_finished_goods_warehouse_not_distributed'):continue
                    if item.get('id')!=path.stem:raise ValueError('PLANNER_ORDER_ID_MISMATCH')
                    objective=item.get('subject');requirements=item.get('acceptance')
                    candidate={'schema':SCHEMA,'kind':'custom','family_id':item['family_id'],
                      'objective':objective,'requirements':requirements,'audience':str(item.get('requesting_site','internal factory')),
                      'language':'fa' if item.get('requesting_site')=='zomorodmelal.ir' else 'en'}
                    candidate=request(candidate,profiles);key=digest(candidate);raw.append(candidate)
                    legacy_aliases.setdefault(key,[]).append(path.stem)
                except (ValueError,OSError,TypeError):rejected.append({'file':path.name,'reason':'unplannable_existing_order'})
        for path in files:
            try:
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}\.json',path.name):raise ValueError('PLANNER_INTAKE_FILENAME')
                raw.append(read(path))
            except (ValueError,OSError,TypeError):rejected.append({'file':path.name,'reason':'invalid_intake_file'})
        unique={}
        for item in raw:
            try:
                req=request(item,profiles);unique[digest(req)]=req
            except (ValueError,TypeError):rejected.append({'reason':'request_schema_or_scope_invalid'})
        rows=[];now=time.time();capacity=resources(root);holds=admissible(capacity)
        selected=sorted(unique.items(),key=lambda item:(item[0] in legacy_aliases,item[0]))[:500]
        for key,req in selected:
            plan=prepare(root,req,profiles[req['family_id']],routes);plan['source_orders']=legacy_aliases.get(key,[]);save(plans/(key+'.json'),plan)
            path=states/(key+'.json');prior=read(path) if path.exists() else {}
            evidence=proof(root,req.get('product_id','invalid'),req['family_id'],proto) if req['kind']=='catalog' else None
            status='native_recipe_verified' if evidence else ('blocked_missing_engineering_or_inputs' if plan['blockers'] else 'queued')
            # Always reconcile proof, not just a persisted success flag.
            row={'plan_id':key,'family_id':req['family_id'],'kind':req['kind'],'status':status,
                 'blockers':plan['blockers'],'proof':evidence,'request':req,
                 'source_orders':legacy_aliases.get(key,[]),'last_execution':prior.get('last_execution'),
                 'last_attempt':prior.get('last_attempt',0),'retry_at':prior.get('retry_at',0),
                 'attempts':prior.get('attempts',0),'commercial_release':False}
            rows.append(row)
        queued=sorted((r for r in rows if r['status']=='queued' and r['retry_at']<=now),key=lambda r:(r['last_attempt'],r['plan_id']))
        executed=0
        if dispatch and not holds:
            for row in queued[:max_execute]:
                row['last_attempt']=now;row['attempts']+=1
                try:result=execute(root,row['request'])
                except OSError:result={'status':'launch_failed','retry_after_seconds':300}
                row['last_execution']=result;row['retry_at']=now+min(3600, max(result.get('retry_after_seconds',300),60*2**min(row['attempts'],5)))
                evidence=proof(root,row['request']['product_id'],row['family_id'],proto)
                row['proof']=evidence;row['status']='native_recipe_verified' if evidence else result['status'];executed+=1
        for row in rows:save(states/(row['plan_id']+'.json'),row)
        blockers=Counter(b for row in rows for b in row['blockers'])
        blocked_families=sorted({row['family_id'] for row in rows if row['kind']=='qualification'})
        remediation=[{'family_id':f,'producer_adapter':profiles[f]['producer_adapter'],'required_inputs':routes.INPUTS[f],
          'required_component_pipeline':list(routes.ROUTES[f]),'required_independent_tests':profiles[f]['specialist_tests'],
          'status':'specialist_executor_must_be_implemented_and_validated'} for f in blocked_families]
        report={'schema':'saeit.factory.product-planning-dashboard.v1','registered_family_routes':40,
          'unique_product_plans':len(rows),'deferred_plan_count':max(0,len(unique)-len(rows)),'duplicate_intakes_suppressed':max(0,len(raw)-len(unique)-len(rejected)),
          'existing_orders_scanned':legacy_scanned,'existing_order_plans':len(legacy_aliases),
          'verified_native_product_plans':sum(r['status']=='native_recipe_verified' for r in rows),
          'custom_product_executors_verified':0,'families_awaiting_specialist_executor':blocked_families,
          'engineering_backlog':remediation,'rows':rows,'rejected_inputs':rejected,'bottlenecks':dict(blockers),
          'resource_snapshot':capacity,'resource_holds':holds,'executions_this_tick':executed,
          'execution_limit':max_execute,'commercial_release':False,'observed_unix':now,
          'warning':'Forty engineering routes are planning coverage, not forty working product generators.'}
        save(area/'dashboard.json',report)
        return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--factory-private',required=True);p.add_argument('--registry',required=True);p.add_argument('--dispatch',action='store_true');p.add_argument('--max-execute',type=int,default=1)
    a=p.parse_args();r=cycle(a.factory_private,a.registry,a.dispatch,a.max_execute)
    print('FACTORY_PER_PRODUCT_PLANNER='+json.dumps({k:r.get(k) for k in ('status','registered_family_routes','unique_product_plans','verified_native_product_plans','executions_this_tick','resource_holds')},sort_keys=True))
