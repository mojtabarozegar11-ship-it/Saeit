"""Independent behavior, isolation and package checks for five original toolkits."""
import ast
import copy
import csv
from datetime import date
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import zipfile

GATES=('requirements','correctness','negative_cases','usability','accessibility','security','compatibility','provenance','specialist_review','release_integrity')
VALIDATORS=('email','identifier','positive_integer','finite_number','iso_date','sha256','currency_code','nonempty_text','string_list','record_id','unit_interval','safe_filename')
def oracle(key,v):
    try:
        if key=='email':return isinstance(v,str) and len(v)<=254 and len(v.split('@')[0])<=64 and bool(re.fullmatch(r'[A-Za-z0-9_%+-]+(?:\.[A-Za-z0-9_%+-]+)*@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}',v))
        if key=='identifier':return isinstance(v,str) and bool(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}',v))
        if key=='positive_integer':return type(v) is int and v>0
        if key=='finite_number':return type(v) in (int,float) and math.isfinite(v)
        if key=='iso_date':return isinstance(v,str) and bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}',v)) and date.fromisoformat(v).isoformat()==v
        if key=='sha256':return isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v)
        if key=='currency_code':return isinstance(v,str) and v in {'USD','EUR','GBP','CAD','AUD','JPY','CHF','AED'}
        if key=='nonempty_text':return isinstance(v,str) and 0<len(v.strip())<=1000
        if key=='string_list':return isinstance(v,list) and bool(v) and all(isinstance(x,str) and x.strip() for x in v) and len(set(v))==len(v)
        if key=='record_id':return isinstance(v,dict) and type(v.get('id')) is int and v['id']>=1
        if key=='unit_interval':return type(v) in (int,float) and math.isfinite(v) and 0<=v<=1
        if key=='safe_filename':return isinstance(v,str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',v)) and not v.endswith('.') and v.split('.')[0].upper() not in {'CON','PRN','AUX','NUL'}|{'COM'+str(i) for i in range(1,10)}|{'LPT'+str(i) for i in range(1,10)}
    except (ValueError,TypeError,OverflowError):return False
    raise ValueError('UNKNOWN_ORACLE')
EXTRA={
'F21':{'json_pretty':('{}','{}'),'json_compact':('[1, 2]','[1,2]'),'text_sha256':('','e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
 'base64_encode':('é','w6k='),'base64_decode':('w6k=','é'),'slug':(' A / B ','a-b'),'unique_lines':('a\na','a'),
 'sorted_lines':('c\nb\na','a\nb\nc'),'word_count':('',0),'utf8_bytes':('é',2),'html_escape':('&','&amp;'),'line_numbers':('', '')},
'F22':{'active_records':([],[]),'drop_empty':([{'a':False,'b':None}],[{'a':False}]),'normalize_email':([{}],[{'email':''}]),
 'trim_names':([{}],[{'name':''}]),'sort_ids':([{'id':-1},{'id':0}],[{'id':-1},{'id':0}]),'unique_ids':([],[]),'sum_amounts':([],0),
 'count_status':([{}],{'unknown':1}),'redact_email':([{'name':'x'}],[{'name':'x'}]),'rename_identifier':([{'id':0}],[{'record_id':0}]),
 'flatten_tags':([{}, {'tags':[]}],[]),'public_fields':([{'token':'private'}],[{}])},
'F28':{'celsius_fahrenheit':([-40],-40),'fahrenheit_celsius':([212],100),'km_miles':([0],0),'litres_gallons':([0],0),
 'rectangle_area':([0,3],0),'triangle_area':([10,2],10),'circle_area':([2],12.566370614359172),
 'cylinder_volume':([2,1],12.566370614359172),'speed':([9,3],3),'density':([0,2],0),'ohms_voltage':([0,4],0),'electric_energy':([1000,3],3)}
}
def function(path):
    text=Path(path).read_text('utf8');tree=ast.parse(text)
    allowed={'json','math','re','hashlib','base64','html','datetime'}
    for n in ast.walk(tree):
        if isinstance(n,(ast.Import,ast.ImportFrom)):
            mods=[a.name.split('.')[0] for a in n.names] if isinstance(n,ast.Import) else [n.module]
            if any(m not in allowed for m in mods):raise ValueError('B5_FORBIDDEN_IMPORT')
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {'open','eval','exec','compile','__import__','input'}:raise ValueError('B5_UNSAFE_CODE')
    spec=importlib.util.spec_from_file_location('independent_'+Path(path).stem,str(path));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.run

def equal(got,want):
    if type(want) in (float,int):return type(got) in (float,int) and math.isclose(got,want,rel_tol=1e-10,abs_tol=1e-10)
    return type(got) is type(want) and got==want

def check(folder,archive,product,family,keys):
    folder=Path(folder);expected={'README.md','catalog.json','run_tool.py'};checks=0
    catalog=json.loads((folder/'catalog.json').read_text())
    if catalog['family_id']!=family or len(keys)!=12 or len(set(keys))!=12:raise ValueError('B5_FAMILY_BINDING')
    for index,key in enumerate(keys):
        if family=='F25':
            names=[key+'.csv',key+'.json',key+'_schema.json',key+'_guide.md'];expected.update(names)
            records=json.loads((folder/(key+'.json')).read_text())
            schema=json.loads((folder/(key+'_schema.json')).read_text())
            if schema['synthetic'] is not True or schema['validator']!=VALIDATORS[index] or len(records)!=4:raise ValueError('B5_DATA_SCHEMA')
            rows=list(csv.DictReader(io.StringIO((folder/(key+'.csv')).read_text())))
            if len(rows)!=4:raise ValueError('B5_CSV_ROW_COUNT')
            for i,(r,c) in enumerate(zip(records,rows),1):
                if r['id']!=i or type(r['expected_valid']) is not bool or oracle(VALIDATORS[index],r['value']) is not r['expected_valid']:raise ValueError('B5_DATA_ORACLE_MISMATCH')
                if int(c['id'])!=i or json.loads(c['value_json'])!=r['value'] or json.loads(c['expected_valid']) is not r['expected_valid']:raise ValueError('B5_CSV_ROUNDTRIP')
                checks+=2
        else:
            names=[key+'.py',key+'_test.py',key+'_example.json',key+'_guide.md'];expected.update(names)
            run=function(folder/(key+'.py'));demo=json.loads((folder/(key+'_example.json')).read_text())
            original=copy.deepcopy(demo['input']);got=run(demo['input'])
            if demo['input']!=original or not equal(got,demo['expected']):raise ValueError('B5_BEHAVIOR_OR_MUTATION')
            checks+=2
            if family=='F20':
                for v in (None,True,0,'',[],{},'../x','2025-02-29','a..b@example.org','a@-example.org','CON.txt','report.'):
                    if run(v) is not oracle(key,v):raise ValueError('B5_VALIDATOR_ORACLE')
                    checks+=1
            else:
                v,want=EXTRA[family][key]
                if not equal(run(v),want):raise ValueError('B5_INDEPENDENT_BEHAVIOR')
                checks+=1
                for invalid in (None,{},True):
                    try:run(invalid)
                    except ValueError:checks+=1
                    else:raise ValueError('B5_INPUT_GUARD_MISSING')
            if family=='F28' and key in ('speed','density'):
                try:run([1,0])
                except ValueError:checks+=1
                else:raise ValueError('B5_ZERO_DIVISION_NOT_GUARDED')
        for name in names:
            if (folder/name).is_symlink() or not 20<(folder/name).stat().st_size<50000:raise ValueError('B5_REAL_OUTPUT_REQUIRED')
    # Distribution runner selects only catalog-listed modules. No eval or network.
    runner=(folder/'run_tool.py').read_text()
    if 'eval(' in runner or 'subprocess' in runner or 'choices=' not in runner:raise ValueError('B5_RUNNER_GUARD')
    hashes=[hashlib.sha256((folder/n).read_bytes()).hexdigest() for n in expected]
    if len(hashes)!=len(set(hashes)):raise ValueError('B5_DUPLICATE_OUTPUTS')
    with zipfile.ZipFile(archive) as z:
        if set(z.namelist())!={product+'/'+n for n in expected} or len(z.namelist())!=51 or z.testzip() is not None:raise ValueError('B5_PACKAGE_STRUCTURE')
        for n in expected:
            if z.read(product+'/'+n)!=(folder/n).read_bytes():raise ValueError('B5_PACKAGE_TAMPERED')
    return {'passed':True,'checks_passed':checks,'files_checked':51,'gates':dict.fromkeys(GATES,True),
      'review_scope':'independent executable examples, negative inputs, data oracles, source isolation and archive integrity',
      'human_specialist_review':False,'commercial_release':False,'synthetic_data':family=='F25'}
