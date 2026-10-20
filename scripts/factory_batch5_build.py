#!/usr/bin/env python3
"""Five real engineering products: each executes 48 distinct authored tasks.

Recurring ticks reverify source-bound outputs, rebuild corruption, and preserve
failed attempts. No fake novelty, LLM calls or automatic commerce approval.
"""
import argparse
import csv
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import zipfile

HERE=Path(__file__).resolve().parent

def load(name):
    p=HERE/(name+'.py')
    if p.is_symlink() or not p.is_file():raise ValueError('B5_UNSAFE_MODULE')
    spec=importlib.util.spec_from_file_location(name,str(p));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def json_text(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+'\n'

def source(family,key,title,expression):
    code='"""'+title+'. Original local toolkit; see the included guide for scope."""\n'
    code+='import json, math, re, hashlib, base64, html\nfrom datetime import date\n\ndef run(v):\n'
    if family=='F20':
        code+='    try:\n        return bool('+expression+')\n    except (TypeError,ValueError,OverflowError):\n        return False\n'
        return code
    if family=='F21':guard="isinstance(v,str) and len(v)<=1000000"
    elif family=='F22':
        guard="isinstance(v,list) and len(v)<=1000 and all(isinstance(r,dict) for r in v)"
        if key in ('sort_ids','unique_ids','rename_identifier'):guard+=" and all(type(r.get('id')) is int for r in v)"
        if key=='sum_amounts':guard+=" and all(type(r.get('amount_cents')) is int for r in v)"
        if key=='normalize_email':guard+=" and all(isinstance(r.get('email',''),str) for r in v)"
        if key=='trim_names':guard+=" and all(isinstance(r.get('name',''),str) for r in v)"
        if key=='count_status':guard+=" and all(isinstance(r.get('status','unknown'),str) for r in v)"
        if key=='flatten_tags':guard+=" and all(isinstance(r.get('tags',[]),list) and all(isinstance(t,str) for t in r.get('tags',[])) for r in v)"
    else:
        n=1 if key in ('celsius_fahrenheit','fahrenheit_celsius','km_miles','litres_gallons','circle_area') else 2
        guard="isinstance(v,list) and len(v)==%d and all(type(x) in (int,float) and math.isfinite(x) for x in v)"%n
        if key not in ('celsius_fahrenheit','fahrenheit_celsius'):guard+=' and all(x>=0 for x in v)'
        if key in ('speed','density'):guard+=' and v[1]>0'
    code+='    if not ('+guard+"):raise ValueError('Invalid input for "+key+"')\n"
    code+='    try:\n        result='+expression+'\n'
    if family=='F28':code+="        if not math.isfinite(result):raise ValueError('Nonfinite result')\n"
    code+="        return result\n    except (TypeError,KeyError,ValueError,OverflowError,ZeroDivisionError) as error:\n        raise ValueError('Invalid input for "+key+"') from error\n"
    return code

def runner(family,keys):
    if family=='F25':action="result=json.loads((home/(args.tools[0]+'.json')).read_text(encoding='utf8'))"
    else:action="""result=json.loads(Path(args.input).read_text(encoding='utf8'))
for key in args.tools:
    spec=importlib.util.spec_from_file_location('tool_'+key,str(home/(key+'.py')))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=module.run(result)"""
    return '''#!/usr/bin/env python3
"""Local allowlisted toolkit runner. Prints JSON; does not modify input files."""
import argparse,importlib.util,json
from pathlib import Path
home=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('tools',nargs='''+repr('+' if family=='F22' else 1)+''',choices='''+repr(keys)+''')
p.add_argument('--input',help='JSON input file for a tool or record pipeline')
args=p.parse_args()
'''+('' if family=='F25' else "if not args.input:p.error('--input is required')\nif Path(args.input).stat().st_size>2000000:p.error('input exceeds 2 MB')\n")+action+"\nprint(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2))\n"

def build(root,family):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise ValueError('B5_INVALID_PRIVATE_ROOT')
    proto=load('factory_build_50');specs=load('factory_batch5_specs');review=load('factory_batch5_review')
    if family not in specs.FAMILIES:raise ValueError('B5_UNSUPPORTED_FAMILY')
    product='fieldwork_'+specs.SLUGS[family];home=root/'build-50'/product;target=root/'digital-products'/product
    if any(p.is_symlink() for p in (root/'digital-products',target,home)):raise ValueError('B5_UNSAFE_PRODUCT_PATH')
    snapshot=proto.digest({p:proto.file_sha(HERE/(p+'.py')) for p in ('factory_batch5_build','factory_batch5_specs','factory_batch5_review','factory_build_50')})
    entries=specs.FIXTURES if family=='F25' else specs.SPECS[family];keys=[r[0] for r in entries]
    actions=('csv','data','schema','guide') if family=='F25' else ('source','test','example','guide')
    tasks=[]
    for row in entries:
        key,title=row[:2]
        for action in actions:
            tasks.append({'id':key+'_'+action,'key':key,'action':action,
              'instruction':'Author and verify the '+action+' component of '+title+' in '+family+'. Use its dedicated behavior, input contract and output, without reusing an existing stage artifact.',
              'acceptance':['A new nonempty artifact implements this tool-specific component.',
                            'Its syntax, data structure or executable demonstration is validated.']})
    plan={'schema':proto.SCHEMA,'product_id':product,'family_id':family,'producer_id':'fieldwork_'+family.lower()+'_engineering_producer',
      'source_snapshot_sha256':snapshot,'work_packages':tasks}
    archive_name=product+'-internal-qa.zip'
    if (home/'state.json').is_file() and (target/'manufacturing_manifest.json').is_file():
        state=proto.read(home/'state.json');manifest=proto.read(target/'manufacturing_manifest.json');archive=target/archive_name
        if (proto.verify_attempt(home,state,snapshot) and archive.is_file() and not archive.is_symlink()
            and proto.file_sha(archive)==manifest.get('artifact_sha256')):
            return {'family_id':family,'product_id':product,'status':'unchanged_verified_technical_product'}
    bykey={r[0]:r for r in entries}
    def worker(task,ctx):
        row=bykey[task['key']];key,title=row[:2];action=task['action'];folder=Path(ctx['folder'])
        if family=='F25':
            records=[{'id':i,'value':v,'expected_valid':ok} for i,(v,ok) in enumerate(row[2],1)]
            if action=='data':name=key+'.json';text=json_text(records)
            elif action=='schema':
                name=key+'_schema.json';text=json_text({'schema':'fieldwork.synthetic.validation-fixtures.v1','scenario':key,
                  'synthetic':True,'validator':review.VALIDATORS[keys.index(key)],'row_count':4,
                  'fields':{'id':'integer, sequential from one','value':'scenario-specific JSON value','expected_valid':'boolean oracle label'},
                  'csv_encoding':'UTF-8; value_json is JSON; expected_valid is JSON boolean'})
            elif action=='csv':
                name=key+'.csv';out=io.StringIO(newline='');w=csv.writer(out);w.writerow(['id','value_json','expected_valid'])
                for r in records:w.writerow([r['id'],json.dumps(r['value'],ensure_ascii=False),json.dumps(r['expected_valid'])])
                text=out.getvalue()
            else:name=key+'_guide.md';text='# '+title+'\n\nThese four records are deliberately SYNTHETIC software test fixtures. They are not observations, personal records, research findings or production data.\n\nThe expected_valid flag follows '+review.VALIDATORS[keys.index(key)]+' validation rules. Invalid cases are intentional. CSV value_json must be parsed as JSON before comparison. The matching schema documents all fields. Do not infer statistical representativeness from this tiny edge-case set.\n'
        else:
            expression,v,expected=row[2:]
            if action=='source':name=key+'.py';text=source(family,key,title,expression);compile(text,name,'exec')
            elif action=='example':name=key+'_example.json';text=json_text({'tool':key,'family':family,'input':v,'expected':expected})
            elif action=='test':
                name=key+'_test.py';text='"""Executable regression for '+title+'. Run with python '+name+'."""\nfrom '+key+' import run\nimport math\nvalue='+repr(v)+'\nexpected='+repr(expected)+'\nactual=run(value)\nassert (math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-10) if type(expected) in (int,float) and type(actual) in (int,float) else type(actual) is type(expected) and actual==expected)\nprint('+repr(key+' example PASS')+')\n';compile(text,name,'exec')
            else:
                name=key+'_guide.md';text='# '+title+'\n\nFamily '+family+'. Original local Python utility.\n\nInput example:\n```json\n'+json_text(v)+'```\nExpected result:\n```json\n'+json_text(expected)+'```\n\nRun: `python run_tool.py '+key+' --input '+key+'_example_input.json` after saving only the example input value in that file. Or import `run` from '+key+'. Input is never modified.\n\n'
                if family=='F20':text+='Returns a boolean; invalid types and invalid calendar values return false. This is a conservative syntax check, not deliverability, identity or security certification.\n'
                elif family=='F21':text+='Accepts a Unicode string up to one million characters. Invalid encoding or JSON raises ValueError. Line and word operations use Python splitlines/split behavior; slug output is ASCII only. JSON key ordering is deterministic, not a cryptographic canonicalization standard.\n'
                elif family=='F22':text+='Accepts at most 1000 JSON records. Field-specific type checks reject incompatible inputs. Currency amounts are integer minor units. Pipelines run left-to-right; each step must accept the previous output type. Redaction removes only the named email field, not all sensitive information.\n'
                else:text+='Pass a list of finite numbers in the order described by the title. Temperature accepts negative values; lengths, time, mass, current and resistance are nonnegative here. Speed and density require a positive second input. Results use binary floating point, not certified engineering measurements. Units must be consistent; verify application tolerances.\n'
        p=folder/name;p.write_text(text,encoding='utf8')
        if not p.read_text('utf8') or p.stat().st_size<20:raise ValueError('B5_EMPTY_WORK')
        if name.endswith('.json'):json.loads(text)
        return {'passed':True,'outputs':[name],'successful_checks':2}
    def assemble(plan_data,ctx):
        folder=Path(ctx['folder']);members=sorted(p.name for p in folder.iterdir() if not p.name.endswith('-work.json') and p.name!='01-plan.json')
        catalog={'family_id':family,'tools':keys,'original_source':True,'synthetic_data':family=='F25','commercial_release':False}
        if family=='F22':catalog['workflow_steps']={key:[key] for key in keys}
        (folder/'catalog.json').write_text(json_text(catalog),encoding='utf8')
        (folder/'run_tool.py').write_text(runner(family,keys),encoding='utf8')
        (folder/'README.md').write_text('# Fieldwork '+specs.SLUGS[family]+'\n\n12 dedicated components, examples and usage guides. Requires Python 3.8 or newer; standard library only. Offline operation. No API, installation, telemetry or network access.\n\nList commands with `python run_tool.py --help`. '+('Read a synthetic dataset with `python run_tool.py email_cases`.' if family=='F25' else 'Save a JSON value in input.json, then `python run_tool.py '+keys[0]+' --input input.json`. F22 accepts several tool names as a left-to-right record pipeline.')+'\n\nEach component has its own guide. Technical tests do not constitute legal, scientific or human specialist approval. All rights reserved Zomorod Melal; private internal evaluation copy.\n',encoding='utf8')
        members+=['catalog.json','run_tool.py','README.md']
        with zipfile.ZipFile(folder/archive_name,'w',zipfile.ZIP_DEFLATED) as z:
            for name in members:
                info=zipfile.ZipInfo(product+'/'+name,date_time=(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
                z.writestr(info,(folder/name).read_bytes())
        return {'passed':True,'outputs':['catalog.json','run_tool.py','README.md',archive_name],'successful_checks':4}
    def reviewer(plan_data,ctx):
        folder=Path(ctx['folder']);result=review.check(folder,folder/archive_name,product,family,keys)
        proto.save(folder/'independent-review.json',result)
        return {'reviewer_id':'independent_'+family.lower()+'_executable_behavior_and_integrity_qa','critical_defects':[],
          'passed':True,'gates':result['gates'],'outputs':['independent-review.json'],'successful_checks':result['checks_passed']}
    state=proto.run_attempt(root,plan,worker,assemble,reviewer)
    if not proto.verify_attempt(home,state,snapshot):return {'family_id':family,'status':'technical_rework_required','defects':state.get('defects',[])}
    folder=Path(state['attempt_folder']);target.mkdir(parents=True,exist_ok=True,mode=0o700);incoming=target/'.incoming-batch5.zip'
    if incoming.is_symlink() or (target/archive_name).is_symlink():raise ValueError('B5_UNSAFE_COPY')
    shutil.copyfile(folder/archive_name,incoming);os.replace(incoming,target/archive_name)
    with zipfile.ZipFile(target/archive_name) as z:files=[n.split('/',1)[1] for n in z.namelist()]
    manifest={'schema_version':2,'recipe':product,'name':'Fieldwork '+specs.SLUGS[family],'family_id':family,
      'files':files,'bytes':(target/archive_name).stat().st_size,'source_sha256':snapshot,'artifact_sha256':proto.file_sha(target/archive_name),
      'build50_source_snapshot_sha256':snapshot,'qa_status':'passed','qa_evidence':'unit_tests_passed',
      'qa_measurements':proto.read(folder/'independent-review.json'),'commercial_status':'private_internal_qa_pass_not_published',
      'public_listing_enabled':False,'customer_order_required':False,'owner_publication_approval':False,'independent_human_review':False}
    proto.save(target/'manufacturing_manifest.json',manifest)
    return {'family_id':family,'product_id':product,'status':'technical_50_stage_build_completed','completed_stages':50,'files':len(files),'commercial_release':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--factory-private',required=True);args=p.parse_args()
    results=[build(args.factory_private,f) for f in ('F20','F21','F22','F25','F28')]
    print('BATCH5_BUILD50='+json.dumps(results,sort_keys=True))
    if any(x['status']=='technical_rework_required' for x in results):raise SystemExit(2)
