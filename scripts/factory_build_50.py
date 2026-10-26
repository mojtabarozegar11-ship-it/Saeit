#!/usr/bin/env python3
"""Evidence-bound 1+48+1 build protocol. No automatic claim of product quality.

Workers must actually execute 48 distinct planned work packages. Failed attempts
are retained and the next attempt restarts at planning with the defect report.
The periodic auditor never fabricates missing worker outputs or expert reviews.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import traceback

SCHEMA='saeit.factory.build-50.v1'
GATES=('requirements','correctness','negative_cases','usability','accessibility',
       'security','compatibility','provenance','specialist_review','release_integrity')
PRODUCT=re.compile(r'^[A-Za-z][A-Za-z0-9_-]{1,90}$')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(65536),b''): h.update(chunk)
    return h.hexdigest()


def read(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>2000000:
        raise ValueError('BUILD50_UNSAFE_INPUT')
    data=json.loads(path.read_text(encoding='utf8'))
    if not isinstance(data,dict):raise ValueError('BUILD50_OBJECT_REQUIRED')
    return data


def save(path,value):
    path=Path(path)
    if path.is_symlink() or path.parent.is_symlink():raise ValueError('BUILD50_UNSAFE_STATE')
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,tmp=tempfile.mkstemp(prefix='.build50-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf8') as f:
            json.dump(value,f,sort_keys=True,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)



def save_if_changed(path,value):
    """Avoid repeated fsync for an unchanged, hash-bound planning receipt.

    Never skip the underlying source/ZIP integrity audit; this only suppresses
    rewriting the same verified JSON. Unsafe existing files still fail closed.
    """
    path=Path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('BUILD50_UNSAFE_STATE')
    raw=json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)
    if path.exists():
        if not path.is_file() or path.stat().st_size>2_000_000:
            raise ValueError('BUILD50_UNSAFE_STATE')
        if path.read_text(encoding='utf8')==raw:
            return False
    save(path,value)
    return True


def validate_plan(plan):
    if plan.get('schema')!=SCHEMA or not PRODUCT.fullmatch(str(plan.get('product_id',''))):
        raise ValueError('BUILD50_PLAN_ID_INVALID')
    if not isinstance(plan.get('producer_id'),str) or not plan['producer_id'].strip():
        raise ValueError('BUILD50_PRODUCER_REQUIRED')
    if not re.fullmatch('[a-f0-9]{64}',str(plan.get('source_snapshot_sha256',''))):
        raise ValueError('BUILD50_SOURCE_BINDING_REQUIRED')
    tasks=plan.get('work_packages')
    if not isinstance(tasks,list) or len(tasks)!=48:raise ValueError('BUILD50_REQUIRES_48_WORK_PACKAGES')
    ids=set(); instructions=set()
    for task in tasks:
        if not isinstance(task,dict):raise ValueError('BUILD50_TASK_OBJECT_REQUIRED')
        ident=task.get('id');instruction=task.get('instruction');criteria=task.get('acceptance')
        if not isinstance(ident,str) or not re.fullmatch(r'[a-z][a-z0-9_]{2,63}',ident) or ident in ids:
            raise ValueError('BUILD50_DISTINCT_TASK_IDS_REQUIRED')
        normalized=re.sub(r'\d+','<number>',instruction.strip().casefold()) if isinstance(instruction,str) else ''
        if not isinstance(instruction,str) or not 40<=len(instruction)<=6000 or normalized in instructions:
            raise ValueError('BUILD50_DISTINCT_SUBSTANTIVE_INSTRUCTIONS_REQUIRED')
        if (not isinstance(criteria,list) or len(criteria)<2
                or any(not isinstance(c,str) or len(c.strip())<12 for c in criteria)):
            raise ValueError('BUILD50_ACCEPTANCE_CRITERIA_REQUIRED')
        ids.add(ident);instructions.add(normalized)
    return tasks


def measured_outputs(folder,result):
    """Receipts bind actual nonempty files; worker success flags alone cannot pass."""
    if not isinstance(result,dict) or result.get('passed') is not True:
        raise ValueError('BUILD50_WORK_NOT_PASSED')
    files=result.get('outputs')
    tests=result.get('successful_checks')
    if not isinstance(files,list) or not files or type(tests) is not int or tests<1:
        raise ValueError('BUILD50_MEASURED_WORK_REQUIRED')
    outputs={}
    root=Path(folder).resolve()
    for name in files:
        if not isinstance(name,str) or not name or '\\' in name or '..' in Path(name).parts or Path(name).is_absolute():
            raise ValueError('BUILD50_UNSAFE_OUTPUT')
        if len(Path(name).parts)==1 and re.fullmatch(r'(?:01-plan|(?:0[2-9]|[1-4][0-9])-work|50-summary|rejection)\.json',name):
            raise ValueError('BUILD50_RESERVED_EVIDENCE_OUTPUT')
        path=root/name
        path.resolve().relative_to(root)
        if path.is_symlink() or not path.is_file() or not 1<=path.stat().st_size<=8000000:
            raise ValueError('BUILD50_REAL_OUTPUT_REQUIRED')
        if name in outputs:raise ValueError('BUILD50_DUPLICATE_OUTPUT')
        outputs[name]=file_sha(path)
    return outputs


def run_attempt(root,plan,worker,assembler,reviewer,now=None):
    validate_plan(plan);root=Path(root);home=root/'build-50'/plan['product_id']
    if any(p.is_symlink() for p in (root,root/'build-50',home)):
        raise ValueError('BUILD50_UNSAFE_ROOT')
    home.mkdir(parents=True,exist_ok=True,mode=0o700)
    if (home/'.attempt.lock').is_symlink():raise ValueError('BUILD50_UNSAFE_LOCK')
    with (home/'.attempt.lock').open('a+b') as lock:
        os.fchmod(lock.fileno(),0o600)
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'status':'already_running','commercial_release':False}
        return _run_attempt(root,plan,worker,assembler,reviewer,now)


def _run_attempt(root,plan,worker,assembler,reviewer,now=None):
    """Trusted producer adapters implement callbacks. Audit never invokes fake work.

    This method executes work; the CLI audit below only identifies missing proof.
    A failed callback or final gate invalidates the entire attempt, preserving files.
    """
    tasks=validate_plan(plan);now=time.time() if now is None else now
    root=Path(root);product=plan['product_id'];home=root/'build-50'/product
    state_path=home/'state.json';prior=read(state_path) if state_path.exists() else {}
    if prior.get('status')=='rework_required' and prior.get('plan_sha256')==digest(plan) and now<prior.get('retry_at',0):
        return dict(prior,deferred=True)
    prior_number=prior.get('attempt',0)
    if type(prior_number) is not int or prior_number<0:raise ValueError('BUILD50_INVALID_ATTEMPT_STATE')
    existing=[int(p.name[8:]) for p in home.glob('attempt-*')
              if re.fullmatch(r'attempt-[0-9]{8,}',p.name)]
    latest=max(existing,default=0)
    previous_defects=list(prior.get('defects',[]))
    # A killed process may leave a real attempt before state.json was committed.
    # Never reuse that folder or get stuck permanently on FileExistsError.
    if latest>prior_number:
        interrupted={'failed_stage':None,'reason':'BUILD50_INTERRUPTED_ATTEMPT',
                     'retained_attempt':latest,'return_to_stage':1}
        previous_defects.append(interrupted)
        save(home/('interrupted-%08d.json'%latest),interrupted)
    number=max(prior_number,latest)+1
    attempt=home/('attempt-%08d'%number);attempt.mkdir(parents=True,mode=0o700)
    receipts=[];current=1
    context={'product_id':product,'attempt':number,'folder':str(attempt),
             'previous_defects':previous_defects,'plan_sha256':digest(plan)}
    save(attempt/'01-plan.json',plan)
    receipts.append({'stage':1,'kind':'planning','plan_sha256':digest(plan)})
    try:
        claimed_paths=set();claimed_hashes=set()
        for stage,task in enumerate(tasks,2):
            current=stage
            before={str(p.relative_to(attempt)):file_sha(p) for p in attempt.rglob('*')
                    if p.is_file() and not p.is_symlink()}
            result=worker(task,dict(context,stage=stage,prior_receipts=list(receipts)))
            outputs=measured_outputs(attempt,result)
            if result['successful_checks']<len(task['acceptance']):raise ValueError('BUILD50_INSUFFICIENT_ACCEPTANCE_CHECKS')
            if claimed_paths.intersection(outputs) or claimed_hashes.intersection(outputs.values()):
                raise ValueError('BUILD50_REUSED_WORK_OUTPUT')
            if any(before.get(name)==checksum for name,checksum in outputs.items()):
                raise ValueError('BUILD50_NO_NEW_WORK_OUTPUT')
            claimed_paths.update(outputs);claimed_hashes.update(outputs.values())
            receipt={'stage':stage,'task_id':task['id'],'outputs':outputs,
                     'files_created_or_changed_in_stage':True,
                     'successful_checks':result['successful_checks'],'previous_sha256':digest(receipts[-1])}
            save(attempt/('%02d-work.json'%stage),receipt);receipts.append(receipt)
        current=50
        # Recheck every file after all workers: later stages cannot rewrite prior proof.
        for receipt in receipts[1:]:
            for name,checksum in receipt['outputs'].items():
                if file_sha(attempt/name)!=checksum:raise ValueError('BUILD50_PRIOR_WORK_MUTATED')
        assembled=assembler(plan,dict(context,stage=50,prior_receipts=list(receipts)))
        outputs=measured_outputs(attempt,assembled)
        if claimed_paths.intersection(outputs) or claimed_hashes.intersection(outputs.values()):
            raise ValueError('BUILD50_ASSEMBLY_REUSES_WORK')
        review=reviewer(plan,dict(context,stage=50,outputs=outputs,prior_receipts=list(receipts)))
        if not isinstance(review,dict) or review.get('critical_defects')!=[]:
            raise ValueError('BUILD50_CRITICAL_DEFECTS_OR_MISSING_REVIEW')
        if (not isinstance(review.get('reviewer_id'),str) or not review['reviewer_id'].strip()
                or review['reviewer_id']==plan.get('producer_id')):
            raise ValueError('BUILD50_SEPARATE_REVIEW_REQUIRED')
        gates=review.get('gates',{})
        if not isinstance(gates,dict) or any(gates.get(gate) is not True for gate in GATES):
            raise ValueError('BUILD50_QUALITY_GATES_NOT_PASSED')
        review_outputs=measured_outputs(attempt,review)
        if (set(review_outputs).intersection(claimed_paths | set(outputs))
                or set(review_outputs.values()).intersection(claimed_hashes | set(outputs.values()))):
            raise ValueError('BUILD50_REVIEW_REUSES_PRODUCTION_OUTPUT')
        if review['successful_checks']<len(GATES):raise ValueError('BUILD50_INSUFFICIENT_QUALITY_CHECKS')
        for receipt in receipts[1:]+[{'outputs':outputs}]:
            for name,checksum in receipt['outputs'].items():
                if file_sha(attempt/name)!=checksum:raise ValueError('BUILD50_WORK_MUTATED_DURING_REVIEW')
        # Review is evidence, not universal proof of scientific/commercial quality.
        final={'stage':50,'kind':'assembly_and_quality_review','outputs':outputs,'review':review,
               'review_outputs':review_outputs,
               'previous_sha256':digest(receipts[-1])}
        save(attempt/'50-summary.json',final);receipts.append(final)
        status='awaiting_owner_acceptance';defects=[]
    except Exception as error:
        frames=traceback.extract_tb(error.__traceback__)
        location=(Path(frames[-1].filename).name+':'+str(frames[-1].lineno)) if frames else 'unknown'
        status='rework_required';defects=[{'failed_stage':current,'reason':type(error).__name__+':'+str(error)[:600],
                                          'failure_location':location}]
        save(attempt/'rejection.json',{'defects':defects,'return_to_stage':1,'retain_outputs':True})
    state={'schema':SCHEMA,'product_id':product,'attempt':number,'status':status,
           'completed_stages':len(receipts),'next_stage':1 if defects else None,
           'plan_sha256':digest(plan),'defects':defects,'retry_at':now+60 if defects else 0,
           'source_snapshot_sha256':plan['source_snapshot_sha256'],
           'final_receipt_sha256':digest(receipts[-1]) if not defects else None,
           'attempt_folder':str(attempt),'lifetime_attempt_limit':None,
           'commercial_release':False,'universal_quality_score':None}
    save(state_path,state);return state


def verify_attempt(home,state,snapshot):
    try:
        if (state.get('schema')!=SCHEMA or state.get('status')!='awaiting_owner_acceptance'
                or type(state.get('completed_stages')) is not int or state['completed_stages']!=50
                or state.get('defects')!=[] or state.get('next_stage') is not None
                or state.get('product_id')!=Path(home).name):return False
        folder=Path(state['attempt_folder']);folder.resolve().relative_to(Path(home).resolve())
        if folder.is_symlink() or state.get('source_snapshot_sha256')!=snapshot:return False
        plan=read(folder/'01-plan.json');tasks=validate_plan(plan)
        if digest(plan)!=state['plan_sha256'] or plan['product_id']!=Path(home).name:return False
        prior={'stage':1,'kind':'planning','plan_sha256':digest(plan)}
        seen_paths=set();seen_hashes=set()
        for stage,task in enumerate(tasks,2):
            receipt=read(folder/('%02d-work.json'%stage))
            if (receipt.get('stage')!=stage or receipt.get('task_id')!=task['id']
                    or receipt.get('previous_sha256')!=digest(prior)
                    or type(receipt.get('successful_checks')) is not int or receipt['successful_checks']<len(task['acceptance'])):return False
            outputs=receipt['outputs']
            checked=measured_outputs(folder,{'passed':True,'outputs':list(outputs),'successful_checks':1})
            if (checked!=outputs or receipt.get('files_created_or_changed_in_stage') is not True
                    or seen_paths.intersection(outputs) or seen_hashes.intersection(outputs.values())):return False
            seen_paths.update(outputs);seen_hashes.update(outputs.values());prior=receipt
        final=read(folder/'50-summary.json')
        if final.get('previous_sha256')!=digest(prior) or digest(final)!=state.get('final_receipt_sha256'):return False
        review=final.get('review',{})
        if (review.get('critical_defects')!=[] or not isinstance(review.get('reviewer_id'),str)
                or not review['reviewer_id'].strip() or review['reviewer_id']==plan['producer_id']
                or review.get('passed') is not True
                or type(review.get('successful_checks')) is not int
                or review['successful_checks']<len(GATES)):return False
        if any(review.get('gates',{}).get(gate) is not True for gate in GATES):return False
        for key in ('outputs','review_outputs'):
            outputs=final[key]
            if measured_outputs(folder,{'passed':True,'outputs':list(outputs),'successful_checks':1})!=outputs:return False
            if seen_paths.intersection(outputs) or seen_hashes.intersection(outputs.values()):return False
            seen_paths.update(outputs);seen_hashes.update(outputs.values())
        if set(review.get('outputs',[]))!=set(final['review_outputs']):return False
        return True
    except (ValueError,OSError,KeyError,TypeError):return False


def audit(root):
    """Find real technical outputs lacking the 50-stage manufacturing proof.

    Technical artifacts stay intact. No completed stages, approvals or scores are
    manufactured from their existence. Tickets return to planning, not disposal.
    """
    root=Path(root);found=[]
    if root.is_symlink() or (root/'build-50').is_symlink():raise ValueError('BUILD50_UNSAFE_ROOT')
    for p in (root/'digital-products').glob('*/manufacturing_manifest.json'):
        if p.parent.is_symlink():continue
        found.append((p.parent.name,p))
    for p in (root/'family-pilots').glob('F*/*/technical-receipt.json'):
        if p.parent.name.startswith('retained-') or p.parent.is_symlink():continue
        found.append(('pilot_'+p.parent.parent.name+'_'+p.parent.name,p))
    rows=[]
    for product,source in found:
        if not PRODUCT.fullmatch(product):continue
        folder=root/'build-50'/product;state_file=folder/'state.json'
        actual={};integrity=True
        try:receipt=read(source);source_hash=file_sha(source)
        except (ValueError,OSError):receipt={};source_hash='unreadable';integrity=False
        if source.name=='manufacturing_manifest.json':
            files={source.parent.name+'-internal-qa.zip':receipt.get('artifact_sha256')}
        else:files=receipt.get('files',{})
        if not isinstance(files,dict) or not files:integrity=False;files={}
        for name,expected in files.items():
            if not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts:
                integrity=False;continue
            path=source.parent/name
            try:path.resolve().relative_to(source.parent.resolve())
            except ValueError:integrity=False;continue
            if path.is_symlink() or not path.is_file():integrity=False;continue
            actual[name]=file_sha(path)
            integrity=integrity and actual[name]==expected
        snapshot=digest({'receipt':source_hash,'files':actual})
        try:state=read(state_file) if state_file.exists() else {}
        except (ValueError,OSError):state={}
        # Only a worker-run attempt can reach acceptance; technical proofs alone cannot.
        accepted=False
        if state.get('status')=='awaiting_owner_acceptance' and state.get('completed_stages')==50:
            # A concrete producer may bind its plan to immutable build inputs.
            # Its current ZIP must also be one of the verified final-stage outputs.
            binding=receipt.get('build50_source_snapshot_sha256')
            if isinstance(binding,str) and re.fullmatch('[a-f0-9]{64}',binding):
                try:
                    final=read(Path(state['attempt_folder'])/'50-summary.json')
                    if receipt.get('artifact_sha256') in final.get('outputs',{}).values():snapshot=binding
                except (ValueError,OSError,KeyError):pass
            accepted=integrity and verify_attempt(folder,state,snapshot)
        if not accepted:
            ticket={'schema':SCHEMA,'product_id':product,'status':'planning_required',
                    'return_to_stage':1,'required_work_packages':48,'required_total_stages':50,
                    'source_receipt_sha256':source_hash,'reason':'NO_VERIFIED_50_STAGE_BUILD',
                    'source_snapshot_sha256':snapshot,'technical_artifact_integrity':integrity,
                    'original_artifact_retained':True,'quality_approved':False,
                    'commercial_release':False,'lifetime_attempt_limit':None}
            save_if_changed(folder/'planning-request.json',ticket)
        rows.append({'product_id':product,'build_50_verified':accepted,
                     'source_receipt_sha256':source_hash,'source_sha256':receipt.get('source_sha256'),
                     'artifact_sha256':receipt.get('artifact_sha256'),
                     'quality_approved':False,'commercial_release':False})
    result={'schema':SCHEMA,'products':rows,'inspected':len(rows),
            'requiring_replanning':sum(not x['build_50_verified'] for x in rows),
            'verified_50_stage_builds':sum(x['build_50_verified'] for x in rows),
            'quality_multiplier_measured':None,'commercial_release':False}
    save_if_changed(root/'build-50-status.json',result);return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--factory-private',required=True)
    args=parser.parse_args();print('FACTORY_BUILD50='+json.dumps(audit(args.factory_private),sort_keys=True))
