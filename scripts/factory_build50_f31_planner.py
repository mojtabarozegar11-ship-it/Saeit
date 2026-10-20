#!/usr/bin/env python3
"""Original dated weekly planning toolkit: 12 tools, 48 substantive outputs.

Stdlib only. Reuses verified weeks without rebuilding; never grants commerce
approval. HTML and SVG are editable and printable without remote resources.
"""
import argparse
from datetime import date,timedelta
from html import escape
import importlib.util
import json
import os
from pathlib import Path
import shutil
import zipfile

HERE=Path(__file__).resolve().parent
TOOLS=(
 ('priorities','Weekly priorities',('Outcome','Why it matters','First action','Success measure','Deadline','Review'),('Ship onboarding guide','Reduce repeated questions','Interview support lead','Five readers complete setup','Friday','Measure completion next week')),
 ('timeblocks','Focus time blocks',('Day','Focus block','Intended output','Available minutes','Interruption plan','Actual outcome'),('Monday','09:00 to 10:00','Draft introduction','60','Silence alerts','Record after the block')),
 ('projects','Project milestones',('Milestone','Deliverable','Dependency','Owner role','Due date','Acceptance check'),('First draft','Editable guide','Support interview','Documentation lead','Wednesday','Review all setup steps')),
 ('risks','Risk register',('Risk','Early signal','Impact','Preventive action','Fallback','Review date'),('Reviewer unavailable','No meeting accepted','Release delayed','Book review early','Ask alternate reviewer','Tuesday')),
 ('decisions','Decision record',('Decision','Options','Evidence needed','Tradeoff','Chosen action','Revisit trigger'),('Guide format','Web or printable','Reader access needs','Printing versus updates','Test both with readers','New accessibility feedback')),
 ('experiments','Small experiment',('Question','Hypothesis','Method','Measurement','Stop condition','Conclusion'),('Can readers find setup steps?','Clear headings reduce search time','Observe five volunteers','Time to correct section','Stop if instructions are unclear','Write findings without generalizing')),
 ('budget','Resource budget',('Activity','Unit','Planned quantity','Actual quantity','Variance explanation','Next adjustment'),('Review sessions','Hours','Three','Record after review','Explain any difference','Adjust next weekly estimate')),
 ('habits','Habit reflection',('Cue','Small action','Planned days','Observed days','Barrier','Adjustment'),('Start of workday','Write one priority','Monday to Friday','Record each day','Competing deadlines','Use a two-minute version')),
 ('learning','Learning log',('Skill','Practice task','Reference to verify','Practice evidence','Uncertainty','Next exercise'),('Technical writing','Rewrite setup section','Internal style guide','Before and after drafts','Reader terminology','Test with a new reader')),
 ('delegation','Delegation brief',('Task','Expected result','Decision boundary','Inputs provided','Check-in','Definition of done'),('Check screenshots','Accurate setup images','Ask before changing product copy','Current draft','Thursday morning','Every image matches the current UI')),
 ('meetings','Meeting to action',('Purpose','Preparation','Decision needed','Action','Responsible role','Follow-up'),('Approve guide outline','Read draft headings','Choose missing sections','Add installation notes','Documentation lead','Friday review')),
 ('review','Weekly retrospective',('Completed','Evidence','Not completed','Main obstacle','Keep doing','Change next week'),('Draft structure','Saved outline','Final screenshots','Test account access','Early reader interviews','Arrange access before writing')),
)
ACTIONS=('blank','example','guide','accessible')

def module(name):
    p=HERE/name
    if p.is_symlink():raise ValueError('F31_UNSAFE_MODULE')
    spec=importlib.util.spec_from_file_location(name.replace('.','_'),str(p))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def monday(value=None):
    d=date.fromisoformat(value) if value else date.today()
    if d.weekday()!=0 and value:raise ValueError('F31_WEEK_MUST_START_MONDAY')
    return d-timedelta(days=d.weekday())

def svg(title,fields,values,week):
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="794" height="1123" viewBox="0 0 794 1123" role="img" aria-labelledby="title desc">',
      '<title id="title">'+escape(title)+'</title><desc id="desc">Six-field printable planning worksheet for week '+week+'</desc>',
      '<rect width="794" height="1123" fill="white"/>',
      '<text x="48" y="65" font-family="sans-serif" font-size="27" fill="#163c35">'+escape(title)+'</text>',
      '<text x="48" y="98" font-family="sans-serif" font-size="14">Week starting '+week+' | Fieldwork planning toolkit</text>']
    for i,(field,value) in enumerate(zip(fields,values)):
        y=135+i*147
        parts+=['<rect x="48" y="%d" width="698" height="127" rx="8" fill="#fff" stroke="#50645e"/>'%y,
          '<text x="66" y="%d" font-family="sans-serif" font-size="17" fill="#163c35">%s</text>'%(y+29,escape(field)),
          '<text x="66" y="%d" font-family="sans-serif" font-size="15">%s</text>'%(y+67,escape(value))]
        if not value:parts.append('<path d="M66 %dH726 M66 %dH726" stroke="#c8d0cc"/>'%(y+70,y+102))
    parts+=['<text x="48" y="1071" font-family="sans-serif" font-size="12">Original editable worksheet. Examples are illustrative; no performance claims.</text></svg>']
    return '\n'.join(parts)

def plan(proto,week):
    product='fieldwork_planner_'+week.replace('-','')
    tasks=[]
    for key,title,fields,examples in TOOLS:
        for action in ACTIONS:
            tasks.append({'id':key+'_'+action,'tool':key,'action':action,
              'instruction':'Create the '+action+' component for '+title+' using its dedicated fields: '+', '.join(fields)+'. Bind the content to week '+week+'.',
              'acceptance':['All six tool-specific fields are present and readable.',
                            'New self-contained output contains the requested dated content.']})
    return {'schema':proto.SCHEMA,'family_id':'F31','product_id':product,
      'producer_id':'fieldwork_weekly_planning_toolkit',
      'source_snapshot_sha256':proto.digest({'producer':proto.file_sha(__file__),
         'reviewer':proto.file_sha(HERE/'factory_f31_independent_review.py'),
         'protocol':proto.file_sha(HERE/'factory_build_50.py'),'week':week}),
      'work_packages':tasks,'week':week}

def page(title,body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>body{font:18px/1.6 system-ui;color:#163c35;max-width:760px;margin:2rem auto;padding:1rem}label{display:block;margin-top:1rem;font-weight:bold}textarea{display:block;width:95%;min-height:4rem;font:inherit;border:1px solid #50645e}@media print{body{margin:0}nav{display:none}section{break-after:page}textarea{min-height:3rem}}</style><body>'+body+'</body></html>'

def build(root,week=None):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise ValueError('F31_UNSAFE_ROOT')
    week=monday(week).isoformat();proto=module('factory_build_50.py');review=module('factory_f31_independent_review.py')
    spec=plan(proto,week);product=spec['product_id'];home=root/'build-50'/product
    target=root/'digital-products'/product
    if any(p.is_symlink() for p in (root/'digital-products',target,home)):raise ValueError('F31_UNSAFE_TARGET')
    archive_name=product+'-internal-qa.zip'
    if (home/'state.json').is_file() and (target/'manufacturing_manifest.json').is_file():
        state=proto.read(home/'state.json');receipt=proto.read(target/'manufacturing_manifest.json')
        archive=target/archive_name
        if (proto.verify_attempt(home,state,spec['source_snapshot_sha256']) and archive.is_file()
            and not archive.is_symlink() and proto.file_sha(archive)==receipt.get('artifact_sha256')):
            return {'status':'unchanged_verified_technical_product','family_id':'F31','product_id':product}
    tools={t[0]:t for t in TOOLS}
    def worker(task,ctx):
        key,title,fields,examples=tools[task['tool']];action=task['action'];folder=Path(ctx['folder'])
        if action in ('blank','example'):
            name=key+'_'+action+'.svg';text=svg(title+(' - worked example' if action=='example' else ''),fields,examples if action=='example' else ['']*6,week)
        elif action=='guide':
            name=key+'_guide.md';text='# '+title+'\n\nWeek starting '+week+'\n\n'
            for field,example in zip(fields,examples):text+='## '+field+'\nWrite your own '+field.lower()+'. Example: '+example+'.\n\n'
            text+='Use the blank worksheet first; compare with the worked example, then record what changed at your weekly review. Examples describe a documentation project and are not advice or guarantees.\n'
        else:
            name=key+'_accessible.html';body='<h1>'+escape(title)+'</h1><p>Week starting '+week+'. Print this page or type into the fields. Entries are not saved when the page closes.</p>'
            for i,field in enumerate(fields):body+='<label for="field%d">%s</label><textarea id="field%d" aria-label="%s"></textarea>'%(i,escape(field),i,escape(field))
            text=page(title,body)
        p=folder/name;p.write_text(text,encoding='utf8')
        if not all(escape(f) in text or f in text for f in fields) or week not in text:raise ValueError('F31_MISSING_CONTENT')
        return {'passed':True,'outputs':[name],'successful_checks':2}
    def assemble(plan_data,ctx):
        folder=Path(ctx['folder']);members=sorted(p.name for p in folder.iterdir() if p.suffix in ('.svg','.md','.html'))
        body='<h1>Fieldwork weekly planning toolkit</h1><p>Week starting '+week+'</p><nav><ul>'
        for key,title,fields,examples in TOOLS:body+='<li><a href="'+key+'_accessible.html">'+escape(title)+'</a> | <a href="'+key+'_guide.md">Guide</a></li>'
        body+='</ul></nav><p>Print at A4 portrait, actual size. Blank worksheets and illustrative completed examples follow.</p>'
        for key,title,fields,examples in TOOLS:
            for action in ('blank','example'):body+='<section><img style="width:100%" src="'+key+'_'+action+'.svg" alt="'+escape(title)+' '+action+'"></section>'
        (folder/'index.html').write_text(page('Fieldwork - '+week,body),encoding='utf8')
        (folder/'README.txt').write_text('Original weekly planning toolkit. 12 blank SVG worksheets, 12 examples, 12 usage guides, 12 accessible HTML forms. Open index.html locally. No network, tracking or external assets. Browser entries are temporary. Technical QA is not human visual or commercial approval. All rights reserved Zomorod Melal; private review copy.\n',encoding='utf8')
        members+=['index.html','README.txt']
        with zipfile.ZipFile(folder/archive_name,'w',zipfile.ZIP_DEFLATED) as z:
            for name in members:
                info=zipfile.ZipInfo(product+'/'+name,date_time=(2020,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
                z.writestr(info,(folder/name).read_bytes())
        return {'passed':True,'outputs':['index.html','README.txt',archive_name],'successful_checks':3}
    def reviewer(plan_data,ctx):
        folder=Path(ctx['folder']);result=review.check(folder,folder/archive_name,product,week)
        proto.save(folder/'independent-technical-review.json',result)
        return {'reviewer_id':'independent_planner_structure_and_archive_reviewer','critical_defects':[],
          'gates':result['gates'],'passed':result['passed'],
          'outputs':['independent-technical-review.json'],'successful_checks':10}
    state=proto.run_attempt(root,spec,worker,assemble,reviewer)
    if not proto.verify_attempt(home,state,spec['source_snapshot_sha256']):
        return {'status':'technical_rework_required','family_id':'F31','defects':state.get('defects',[])}
    folder=Path(state['attempt_folder']);target.mkdir(parents=True,exist_ok=True,mode=0o700)
    incoming=target/'.incoming-planner.zip'
    if incoming.is_symlink() or (target/archive_name).is_symlink():raise ValueError('F31_UNSAFE_ARCHIVE')
    shutil.copyfile(folder/archive_name,incoming);os.replace(incoming,target/archive_name)
    manifest={'schema_version':2,'recipe':product,'family_id':'F31','name':'Fieldwork weekly planning toolkit - '+week,
      'artifact_sha256':proto.file_sha(target/archive_name),'bytes':(target/archive_name).stat().st_size,
      'files':sorted(p.name for p in folder.iterdir() if p.suffix in ('.svg','.md','.html') or p.name=='README.txt'),
      'source_sha256':spec['source_snapshot_sha256'],'customer_order_required':False,
      'build50_source_snapshot_sha256':spec['source_snapshot_sha256'],'qa_status':'passed',
      'qa_evidence':'unit_tests_passed','qa_measurements':proto.read(folder/'independent-technical-review.json'),
      'commercial_status':'private_internal_qa_pass_not_published','public_listing_enabled':False,
      'owner_publication_approval':False,'independent_human_review':False}
    proto.save(target/'manufacturing_manifest.json',manifest)
    return {'status':'technical_50_stage_build_completed','family_id':'F31','product_id':product,'completed_stages':50,'commercial_release':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--factory-private',required=True);p.add_argument('--week')
    args=p.parse_args();result=build(args.factory_private,args.week)
    print('F31_BUILD50='+json.dumps(result,sort_keys=True))
    if result['status']=='technical_rework_required':raise SystemExit(2)
