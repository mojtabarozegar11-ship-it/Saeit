#!/usr/bin/env python3
"""Offline, provenance-bound bridge from four need channels to executable designs.

Only audited mathematical blueprints can be expanded without a research model.
No heuristic turns arbitrary prose into scientific facts or approved products.
"""
import ast
from decimal import Decimal,localcontext
import fcntl
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import time

SCHEMA='saeit.factory.engineering-brief.v1'
CHANNELS={'site-topic-snapshot':'site_need','customer-intake-snapshot':'customer_request',
          'market-research-snapshot':'market_demand','factory-invention-snapshot':'factory_invention'}
ORIGINS=set(CHANNELS.values())
# Each blueprint has explicit dimensions and a mathematical reference oracle.
BLUEPRINTS={
 'inventory_coverage':('Inventory coverage planner','Available stock divided by daily consumption.',
    [('available','units'),('daily_use','units/day')],'days',lambda a,b:a/b),
 'water_volume':('Water volume planner','Constant measured flow multiplied by operating duration.',
    [('flow','litres/hour'),('duration','hours')],'litres',lambda a,b:a*b),
 'net_margin':('Net margin scenario tool','Scenario revenue minus scenario total cost.',
    [('revenue','currency'),('cost','currency')],'currency',lambda a,b:a-b),
 'labour_capacity':('Labour capacity planner','People multiplied by per-person capacity and duration.',
    [('people','people'),('rate','units/person/hour'),('hours','hours')],'units',lambda a,b,c:a*b*c),
 'unit_margin':('Unit margin scenario tool','Scenario revenue minus cost, divided by produced units.',
    [('revenue','currency'),('cost','currency'),('units','units')],'currency/unit',lambda a,b,c:(a-b)/c),
 'repair_duration':('Repair workload planner','Defect count times minutes per defect divided by workers.',
    [('defects','defects'),('repair_minutes','minutes/defect'),('workers','workers')],'minutes',lambda a,b,c:a*b/c),
}

def module(name):
    path=Path(__file__).with_name(name+'.py')
    spec=importlib.util.spec_from_file_location(name+'_intake',path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def read(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>2000000:raise ValueError('INTAKE_UNSAFE_FILE')
    value=json.loads(path.read_text(encoding='utf8'))
    if not isinstance(value,dict):raise ValueError('INTAKE_OBJECT_REQUIRED')
    return value


def source_evidence(root,record,origin):
    refs=record.get('evidence',[])
    if not isinstance(refs,list) or not 1<=len(refs)<=20:raise ValueError('SOURCE_EVIDENCE_REQUIRED')
    verified=[]
    for ref in refs:
        if not isinstance(ref,dict):raise ValueError('SOURCE_EVIDENCE_INVALID')
        name=ref.get('path');expected=ref.get('sha256')
        if not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('SOURCE_EVIDENCE_PATH')
        path=root/name
        path.resolve().relative_to(root.resolve())
        if path.is_symlink() or not path.is_file() or path.stat().st_size>2000000:raise ValueError('SOURCE_EVIDENCE_MISSING')
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=expected:raise ValueError('SOURCE_EVIDENCE_HASH_MISMATCH')
        verified.append({'path':name,'sha256':actual})
    # Evidence presence proves traceability, not external demand or factual truth.
    # Customer and market sources also require a signed review bound to this record.
    if origin in ('customer_request','market_demand'):
        import hmac
        keyfile=root/'design-source-review.key'
        if keyfile.is_symlink() or not keyfile.is_file() or keyfile.stat().st_mode & 0o077:
            raise ValueError('SOURCE_INDEPENDENT_REVIEW_REQUIRED')
        key=keyfile.read_bytes()
        if len(key)<32:raise ValueError('SOURCE_REVIEW_KEY_INVALID')
        payload={k:v for k,v in record.items() if k!='review_signature'}
        signed=hmac.new(key,digest({'origin':origin,'record':payload}).encode(),'sha256').hexdigest()
        if not hmac.compare_digest(signed,str(record.get('review_signature',''))):raise ValueError('SOURCE_REVIEW_SIGNATURE_INVALID')
    return verified


def expand(brief,origin):
    if not isinstance(brief,dict) or brief.get('schema')!=SCHEMA:raise ValueError('STRUCTURED_ENGINEERING_BRIEF_REQUIRED')
    family=brief.get('family_id','F28')
    if family not in ('F27','F28'):raise ValueError('FAMILY_ADAPTER_NOT_IMPLEMENTED:'+str(family))
    if 'mathematical_definition' in brief:return expand_definition(brief,origin)
    key=brief.get('blueprint')
    if key not in BLUEPRINTS:raise ValueError('NEED_NOT_MAPPED_TO_VERIFIED_BLUEPRINT')
    title,problem,fields,unit,oracle=BLUEPRINTS[key]
    # Disjoint benchmark vectors; oracle uses rational arithmetic, compiler uses Decimal.
    rows=[]
    for n in range(1,9):
        values=[Fraction(11*n+3),Fraction((n*n*7)%19+1),Fraction((n*13)%17+1)][:len(fields)]
        output=oracle(*values)
        rows.append({'inputs':{field[0]:int(v) for field,v in zip(fields,values)},'output':str(float(output))})
    spec={'schema':'saeit.factory.design-request.v1','origin':origin,'family_id':family,
          'kind':'arithmetic_program','title':title,'problem':problem,
          'output_unit':unit,'inputs':[{'name':name,'unit':dimension,'minimum':1,'maximum':1000000} for name,dimension in fields],
          'limitations':'Mathematical scenario only; inputs must be measured by the user. No claim of market demand, scientific adequacy, optimal decisions or financial return.',
          'training_examples':rows[:5],'acceptance_examples':rows[5:],
          'blueprint_id':key,'reference_method':'exact_rational_arithmetic'}
    module('factory_recipe_designer').validate(spec)
    return spec



def expand_definition(brief,origin):
    """Compile a NEW bounded arithmetic requirement; no fixed blueprint catalog.

    Formula is a declared mathematical requirement, not an inferred scientific law.
    An independent Fraction interpreter creates benchmarks for Decimal synthesis.
    """
    definition=brief['mathematical_definition']
    if not isinstance(definition,dict):raise ValueError('MATHEMATICAL_DEFINITION_REQUIRED')
    fields=definition.get('inputs');expression=definition.get('expression')
    if not isinstance(fields,list) or not 1<=len(fields)<=4:raise ValueError('DEFINITION_INPUTS_REQUIRED')
    if not isinstance(expression,str) or not 1<=len(expression)<=160:raise ValueError('DEFINITION_EXPRESSION_INVALID')
    names=[f.get('name') if isinstance(f,dict) else None for f in fields]
    if any(not isinstance(n,str) or not re.fullmatch(r'[a-z][a-z0-9_]{1,47}',n) for n in names) or len(set(names))!=len(names):
        raise ValueError('DEFINITION_INPUT_NAMES_INVALID')
    try:tree=ast.parse(expression,mode='eval')
    except SyntaxError as error:raise ValueError('DEFINITION_EXPRESSION_INVALID') from error
    used=set()
    def count(node):
        if isinstance(node,ast.Expression):return count(node.body)
        if isinstance(node,ast.Name) and node.id in names:used.add(node.id);return 1
        if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
            return 1+count(node.left)+count(node.right)
        raise ValueError('DEFINITION_OPERATOR_NOT_SUPPORTED')
    if count(tree)>7 or used!=set(names):raise ValueError('DEFINITION_COMPLEXITY_OR_UNUSED_INPUT')
    normalized=[]
    designer=module('factory_recipe_designer')
    for field in fields:
        if not isinstance(field.get('unit'),str) or not 1<=len(field['unit'])<=80:raise ValueError('DEFINITION_UNITS_REQUIRED')
        lo=Fraction(designer.number(field.get('minimum',1)));hi=Fraction(designer.number(field.get('maximum',100)))
        if lo>=hi or abs(lo)>10**6 or abs(hi)>10**6:raise ValueError('DEFINITION_DOMAIN_INVALID')
        normalized.append(dict(field,minimum=float(lo),maximum=float(hi)))
    def oracle(node,values):
        if isinstance(node,ast.Expression):return oracle(node.body,values)
        if isinstance(node,ast.Name):return values[node.id]
        a=oracle(node.left,values);b=oracle(node.right,values)
        if isinstance(node.op,ast.Add):return a+b
        if isinstance(node.op,ast.Sub):return a-b
        if isinstance(node.op,ast.Mult):return a*b
        return a/b
    rows=[];seen=set()
    for n in range(1,201):
        values={}
        for i,field in enumerate(normalized):
            lo=Fraction(str(field['minimum']));hi=Fraction(str(field['maximum']))
            value=lo+(hi-lo)*Fraction((n*(11,17,23,31)[i]+n*n*(i+1))%101,100)
            if field.get('integral'):value=Fraction(int(value))
            values[field['name']]=value
        signature=tuple(values[name] for name in names)
        if signature in seen:continue
        seen.add(signature)
        try:output=oracle(tree,values)
        except ZeroDivisionError:continue
        if abs(output)>10**12:continue
        with localcontext() as context:
            context.prec=40
            decimal=lambda v:str(Decimal(v.numerator)/Decimal(v.denominator))
            rows.append({'inputs':{name:decimal(values[name]) for name in names},'output':decimal(output)})
        if len(rows)==13:break
    if len(rows)<13:raise ValueError('DEFINITION_INSUFFICIENT_DISTINCT_FINITE_BENCHMARKS')
    spec={'schema':'saeit.factory.design-request.v1','family_id':brief.get('family_id','F28'),
          'kind':'arithmetic_program','origin':origin,
          'title':definition.get('title','Declared arithmetic scenario tool'),
          'problem':definition.get('problem','Evaluate the explicit input expression '+expression),
          'inputs':normalized,'output_unit':definition.get('output_unit'),
          'limitations':'A declared mathematical scenario, not a discovered scientific law or market claim. Domain and commercial review remain pending.',
          'training_examples':rows[:5],'acceptance_examples':rows[5:],
          'mathematical_definition':expression,'reference_method':'independent_ast_rational_interpreter'}
    module('factory_recipe_designer').validate(spec)
    return spec

def candidates(root,supply):
    """Source identifiers are namespaced; no source may impersonate another channel."""
    for old,origin in CHANNELS.items():
        path=root/'production-order-inputs'/(old+'.json')
        if not path.exists():continue
        try:
            snapshot=read(path)
            if snapshot.get('schema')!='saeit.factory.production-instructions.v1':raise ValueError('SOURCE_SCHEMA_INVALID')
            items=snapshot.get('items')
            if not isinstance(items,list) or len(items)>1000:raise ValueError('SOURCE_BATCH_INVALID')
        except (ValueError,OSError) as error:
            yield origin,'invalid-'+old,{'_input_error':str(error)},str(path);continue
        for item in items:
            yield origin,str(item.get('id','invalid')) if isinstance(item,dict) else 'invalid',item,str(path)
    # Direct, versioned owner/internal briefs: these need not wait for customer orders.
    inbox=root/'engineering-briefs'
    if inbox.exists():
        if inbox.is_symlink():raise ValueError('ENGINEERING_INBOX_UNSAFE')
        for path in sorted(inbox.glob('*.json')):
            try:
                item=read(path);origin=item.get('origin')
                if origin not in ORIGINS:raise ValueError('ORIGIN_INVALID')
            except (ValueError,OSError) as error:
                yield 'factory_invention',path.stem,{'_input_error':str(error)},str(path);continue
            yield origin,str(item.get('id','invalid')),item,str(path)
    # Existing native site orders are ingested once, with their bridge receipt checked.
    for path in sorted((root/'production-instructions/orders').glob('WO-*.json')):
        try:
            item=read(path)
            if item.get('origin') not in CHANNELS:continue
            origin=CHANNELS[item['origin']]
            if item.get('requesting_site'):
                if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}(?:-r[0-9]{5,20})?',str(item.get('bridge_cycle',''))):
                    raise ValueError('SITE_CYCLE_INVALID')
                receipt=read(root/'production-instructions/zomorod-site-order-receipts'/(str(item.get('bridge_cycle'))+'.json'))
                if (receipt.get('schema')!='saeit.zomorod.site-factory-bridge.v1'
                        or receipt.get('site')!=item.get('requesting_site') or item['id'] not in receipt.get('orders',[])):
                    raise ValueError('SITE_RECEIPT_MISMATCH')
        except (ValueError,OSError,KeyError) as error:
            yield 'site_need',path.stem,{'_input_error':str(error)},str(path);continue
        yield origin,str(item['id']),item,str(path)
    # Only research bundles whose current evidence passes the existing gate can
    # enter engineering. Failed dossiers are retained, never auto-approved.
    quality=module('factory_evidence_quality')
    for path in sorted((root/'research-dossiers').glob('product-*/evidence_manifest.json')):
        try:
            bundle=read(path)
            if not bundle.get('engineering_brief'):continue
            assessment=quality.assess(bundle)
            if assessment.get('research_gate_passed') is not True:raise ValueError('RESEARCH_EVIDENCE_NOT_READY')
            origin=bundle.get('engineering_origin','factory_invention')
            if origin not in ORIGINS:raise ValueError('RESEARCH_ORIGIN_INVALID')
            item={'id':'research-'+str(bundle['product_id']),'origin':origin,
                  'design_brief':bundle['engineering_brief'],
                  'evidence':[{'path':str(path.relative_to(root)),
                               'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]}
        except (ValueError,OSError,KeyError) as error:
            yield 'factory_invention',path.parent.name,{'_input_error':str(error)},str(path);continue
        yield origin,item['id'],item,str(path)
    if supply is not None and Path(supply).is_file():
        config=read(Path(supply))
        if config.get('schema')!='saeit.factory.internal-design-supply.v1':raise ValueError('SUPPLY_SCHEMA_INVALID')
        briefs=config.get('briefs')
        if not isinstance(briefs,list) or len(briefs)>100:
            raise ValueError('SUPPLY_BRIEFS_BOUNDED_LIST_REQUIRED')
        for brief in briefs:
            # Content-addressed identities prevent novel owner-authored mathematical
            # definitions (without a blueprint key) from all being named "None".
            if not isinstance(brief,dict):
                yield 'factory_invention','internal-invalid',{'_input_error':'SUPPLY_BRIEF_INVALID'},str(Path(supply))
                continue
            family=str(brief.get('family_id','invalid'))
            base=brief.get('blueprint')
            if base is None:
                base='math-'+digest(brief)[:24]
            ident='internal-'+family+'-'+str(base)
            # Only mathematical internal prototypes; never relabel these as demand.
            yield 'factory_invention',ident,{
                'id':ident,'design_brief':brief,'internal_math_prototype':True},str(Path(supply))


def cycle(root,*,supply=None,limit=10,now=None):
    root=Path(root);now=time.time() if now is None else now
    if type(limit) is not int or not 1<=limit<=100:raise ValueError('INTAKE_LIMIT_INVALID')
    designer=module('factory_recipe_designer');area=root/'engineering-intake';designer.private(area)
    if (area/'.lock').is_symlink():raise ValueError('INTAKE_LOCK_UNSAFE')
    with (area/'.lock').open('a+b') as lock:
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'status':'already_running','enqueued':0}
        counts={o:{'accepted':0,'blocked':0,'replayed':0,'deferred':0} for o in ORIGINS}
        planner_revision=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        rows=[];processed=0;cursor_path=area/'cursor.json'
        try:last=read(cursor_path).get('last_key','')
        except (ValueError,OSError):last=''
        pending=list(candidates(root,supply))
        pending.sort(key=lambda x:(x[0],x[1],digest(x[2])))
        pending=[x for x in pending if x[0]+':'+x[1]>last]+[x for x in pending if x[0]+':'+x[1]<=last]
        for origin,ident,record,source in pending:
            key=digest({'origin':origin,'id':ident,'record':record})
            ticket=area/(key+'.json');prior={}
            if ticket.exists():
                try:prior=read(ticket)
                except (ValueError,OSError):prior={}
            dest=root/'design-intake'/(key+'.json')
            if prior.get('planner_revision')==planner_revision and prior.get('status') in ('queued_for_design','technical_prototype_built') and dest.is_file():
                if hashlib.sha256(dest.read_bytes()).hexdigest()==prior.get('design_file_sha256'):
                    counts[origin]['replayed']+=1;continue
            if prior.get('planner_revision')==planner_revision and prior.get('status')=='blocked_rework' and now<prior.get('retry_at',0):
                counts[origin]['deferred']+=1;continue
            if processed>=limit:continue
            processed+=1;last=origin+':'+ident
            row={'schema':'saeit.factory.engineering-intake.v1','origin':origin,'source_id':ident,
                 'source_path':source,'planner_revision':planner_revision,'source_revision_sha256':digest(record),'commercial_release':False,
                 'attempt':prior.get('attempt',0)+1,'return_to_stage':1,'lifetime_attempt_limit':None}
            try:
                if not isinstance(record,dict):raise ValueError('SOURCE_RECORD_INVALID')
                if '_input_error' in record:raise ValueError(str(record['_input_error'])[:400])
                if not re.fullmatch(r'[A-Za-z0-9_-]{2,100}',ident):raise ValueError('SOURCE_ID_INVALID')
                if record.get('origin',origin) not in (origin,next((k for k,v in CHANNELS.items() if v==origin),None)):
                    raise ValueError('SOURCE_CHANNEL_SPOOF')
                internal=record.get('internal_math_prototype') is True
                # Only the installed supply catalog can assert this exemption.
                if internal and (supply is None or source!=str(Path(supply))):raise ValueError('INTERNAL_SOURCE_SPOOF')
                evidence=[] if internal else source_evidence(root,record,origin)
                spec=expand(record.get('design_brief'),origin)
                spec['upstream']={'origin':origin,'source_id':ident,'record_sha256':digest(record),
                                  'evidence':evidence,'source_path':source}
                designer.save(dest,spec)
                row.update(status='queued_for_design',design_request_sha256=designer.digest(spec),
                           design_file_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                           family_id=spec['family_id'],blueprint=spec.get('blueprint_id','declared_arithmetic_definition'),retry_at=0)
                counts[origin]['accepted']+=1
            except (ValueError,OSError) as error:
                row.update(status='blocked_rework',reason=str(error)[:400],
                           retry_at=now+min(3600,60*2**min(row['attempt']-1,6)))
                counts[origin]['blocked']+=1
            designer.save(ticket,row);rows.append(row)
        designer.save(cursor_path,{'last_key':last})
        registry=[{'family_id':'F%02d'%i,'adapter':'arithmetic_xlsx' if i==27 else 'arithmetic_program' if i==28 else None,
                   'status':'implemented_technical_prototype' if i in (27,28) else 'blocked_no_need_specific_executor'} for i in range(1,41)]
        totals={o:{'queued_for_design':0,'technical_prototype_built':0,'blocked_rework':0} for o in ORIGINS}
        for path in area.glob('*.json'):
            if not re.fullmatch(r'[a-f0-9]{64}\.json',path.name):continue
            saved=read(path)
            if saved.get('origin') in totals and saved.get('status') in totals[saved['origin']]:
                totals[saved['origin']][saved['status']]+=1
        result={'schema':'saeit.factory.engineering-intake-status.v1','status':'needs_rework' if any(x['blocked'] for x in counts.values()) else 'ok',
                'channels':counts,'durable_source_revisions':totals,'enqueued':sum(x['accepted'] for x in counts.values()),'processed':processed,
                'latest_results':rows,'capabilities':registry,'implemented_design_families':['F27','F28'],
                'commercial_release':False,'general_ai_invention':False}
        designer.save(area/'status.json',result);return result


def reconcile(root):
    """Attach real measured QA and artifact hashes; never imply build50 completion."""
    root=Path(root);designer=module('factory_recipe_designer');area=root/'engineering-intake'
    if not area.is_dir():return {'technical_prototypes':0,'functional_products':0}
    with (area/'.lock').open('a+b') as lock:
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'status':'already_running'}
        by_request={}
        for path in (root/'design-state').glob('*.json'):
            value=read(path)
            if value.get('status') in ('recipe_created','equivalent_program_exists'):
                by_request[value.get('request_sha256')]=value.get('result',{})
        rows=[];linked=[]
        for path in area.glob('*.json'):
            if not re.fullmatch(r'[a-f0-9]{64}\.json',path.name):continue
            row=read(path);result=by_request.get(row.get('design_request_sha256'),{})
            recipe=result.get('recipe')
            if not isinstance(recipe,str) or not re.fullmatch(r'(?:synth|sheet)_[a-f0-9]{24}',recipe):continue
            manifest_path=root/'digital-products'/recipe/'manufacturing_manifest.json'
            if not manifest_path.is_file():continue
            manifest=read(manifest_path);artifact=manifest_path.parent/(recipe+'-internal-qa.zip')
            qa=manifest.get('qa_measurements',{})
            if (manifest.get('qa_status')!='passed' or type(qa.get('successful_tests')) is not int
                    or qa['successful_tests']<3 or artifact.is_symlink() or not artifact.is_file()):continue
            actual=hashlib.sha256(artifact.read_bytes()).hexdigest()
            if actual!=manifest.get('artifact_sha256'):continue
            row.update(status='technical_prototype_built',recipe=recipe,
                       functional_sha256=result['functional_sha256'],artifact_sha256=actual,
                       measured_successful_tests=qa['successful_tests'],build50_verified=False,
                       warehouse_acceptance='pending_verified_50_stage_build',commercial_release=False)
            designer.save(path,row);rows.append(row)
            # A native order is not complete just because its technical prototype
            # passed unit tests. Issue a separate, source-bound PRIVATE receipt
            # so engineering can prove which real bytes were produced for which
            # unchanged instruction. Do not modify the authoritative work order.
            order_id=row.get('source_id')
            if not isinstance(order_id,str) or not re.fullmatch(r'WO-[0-9]{8}',order_id):continue
            order_file=root/'production-instructions/orders'/(order_id+'.json')
            try:
                order=read(order_file)
                if (order.get('id')!=order_id or order.get('status')=='completed_verified'
                        or order.get('public_distribution_allowed') is not False
                        or digest(order)!=row.get('source_revision_sha256')):continue
                ticket_key=digest({'origin':row.get('origin'),'id':order_id,'record':order})
                if path.stem!=ticket_key:continue
                design_file=root/'design-intake'/(ticket_key+'.json')
                if design_file.is_symlink() or not design_file.is_file():continue
                if hashlib.sha256(design_file.read_bytes()).hexdigest()!=row.get('design_file_sha256'):continue
                design=read(design_file)
                upstream=design.get('upstream',{})
                if (upstream.get('source_id')!=order_id
                        or upstream.get('record_sha256')!=digest(order)):continue
            except (OSError,ValueError,KeyError,AttributeError):continue
            receipt={'schema':'saeit.factory.work-order-technical-candidate.v1',
                     'work_order':order_id,'source_order_sha256':digest(order),
                     'design_request_sha256':row['design_request_sha256'],
                     'design_file_sha256':row['design_file_sha256'],
                     'recipe':recipe,'artifact_sha256':actual,
                     'measured_successful_tests':qa['successful_tests'],
                     'technical_prototype_verified':True,
                     'work_order_completed_verified':False,
                     'quality_1000_certified':False,'commercial_release':False,
                     'public_distribution_allowed':False}
            receipts=root/'production-instructions/technical-candidate-receipts'
            designer.private(receipts)
            dest=receipts/(order_id+'-'+digest(order)+'.json')
            if dest.exists() and read(dest)!=receipt:continue
            designer.save(dest,receipt)
            linked.append(order_id)
        status={'technical_prototypes':len(set(x['recipe'] for x in rows)),
                'functional_products':len(set(x['functional_sha256'] for x in rows)),
                'source_revisions_with_prototype':len(rows),'commercial_release':False,
                'build50_verified_products':0,
                'native_work_orders_with_source_bound_technical_candidate':len(set(linked)),
                'native_work_orders_completed_verified_by_reconciliation':0}
        designer.save(area/'production-results.json',status);return status
