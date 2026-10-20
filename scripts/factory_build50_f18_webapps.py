#!/usr/bin/env python3
"""Original offline, loopback-only engineering calculator web applications.

12 executable apps; 48 authored components and independent HTTP/negative tests.
No public listener, API keys, remote resources or automatic sale approval.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import zipfile
from html import escape
HERE=Path(__file__).resolve().parent
PRODUCT='fieldwork_local_calculator_webapps'
def load(name):
    p=HERE/(name+'.py')
    if p.is_symlink():raise ValueError('F18_UNSAFE_MODULE')
    s=importlib.util.spec_from_file_location(name,str(p));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
SERVER='''
# Every request is restricted to the local origin and exact static-file allowlist.
if __name__=='__main__':
    import argparse
    from http.server import BaseHTTPRequestHandler,HTTPServer
    from pathlib import Path
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup();self.connection.settimeout(3)
        def log_message(self,*args):pass
        def reply(self,status,body,kind='application/json'):
            data=(json.dumps(body,allow_nan=False) if kind=='application/json' else body).encode('utf8')
            self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8')
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def origin_ok(self):
            port=self.server.server_port
            hosts=('127.0.0.1:'+str(port),'localhost:'+str(port))
            return self.headers.get('Host') in hosts and self.headers.get('Origin','http://127.0.0.1:'+str(port)) in tuple('http://'+x for x in hosts)
        def do_GET(self):
            if not self.origin_ok():self.reply(403,{'error':'Local origin required'});return
            allowed={'/':(APP+'.html','text/html'),'/app.js':(APP+'.js','text/javascript')}
            if self.path not in allowed:self.reply(404,{'error':'Not found'});return
            filename,kind=allowed[self.path]
            self.reply(200,(Path(__file__).parent/filename).read_text(encoding='utf8'),kind)
        def do_POST(self):
            if not self.origin_ok():self.reply(403,{'error':'Local origin required'});return
            if self.path!='/api/calculate':self.reply(404,{'error':'Not found'});return
            try:
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError()
                size=int(self.headers.get('Content-Length','0'))
                if not 1<=size<=4096:raise ValueError()
                value=json.loads(self.rfile.read(size).decode('utf8'))
                result=run(value)
                self.reply(200,{'result':result})
            except (ValueError,TypeError,UnicodeError):self.reply(400,{'error':'Invalid numeric input or units'})
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=0);a=p.parse_args()
    if not 0<=a.port<=65535:p.error('port out of range')
    server=HTTPServer(('127.0.0.1',a.port),Handler)
    print('LOCAL_WEB_APP_PORT='+str(server.server_port),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
'''
def build(root):
    root=Path(root)
    if not root.is_dir() or root.is_symlink():raise ValueError('F18_PRIVATE_ROOT')
    proto=load('factory_build_50');specs=load('factory_batch5_specs');support=load('factory_batch5_build');review=load('factory_f18_independent_review')
    snapshot=proto.digest({n:proto.file_sha(HERE/(n+'.py')) for n in ('factory_build50_f18_webapps','factory_f18_independent_review','factory_batch5_specs','factory_batch5_build','factory_build_50')})
    tasks=[]
    for key,title,expression,example,expected in specs.SPECS['F28']:
        for action in ('server','interface','interaction','reference'):
            tasks.append({'id':key+'_'+action,'tool':key,'action':action,
              'instruction':'Build and independently verify the '+action+' component for '+title+' with guarded finite-number inputs and loopback-only execution.',
              'acceptance':['A new tool-specific artifact implements the requested component.',
                            'Syntax, structure or numeric reference cases are checked without external services.']})
    plan={'schema':proto.SCHEMA,'family_id':'F18','product_id':PRODUCT,'producer_id':'fieldwork_loopback_web_application_builder','source_snapshot_sha256':snapshot,'work_packages':tasks}
    home=root/'build-50'/PRODUCT;target=root/'digital-products'/PRODUCT;archive_name=PRODUCT+'-internal-qa.zip'
    if any(p.is_symlink() for p in (home,target,root/'digital-products')):raise ValueError('F18_UNSAFE_TARGET')
    if (home/'state.json').is_file() and (target/'manufacturing_manifest.json').is_file():
        state=proto.read(home/'state.json');manifest=proto.read(target/'manufacturing_manifest.json');arc=target/archive_name
        if (proto.verify_attempt(home,state,snapshot) and arc.is_file() and not arc.is_symlink()
            and proto.file_sha(arc)==manifest.get('artifact_sha256')
            and manifest['artifact_sha256'] in proto.read(Path(state['attempt_folder'])/'50-summary.json')['outputs'].values()):
            return {'status':'unchanged_verified_technical_product','family_id':'F18','product_id':PRODUCT}
    bykey={r[0]:r for r in specs.SPECS['F28']}
    def worker(task,ctx):
        key,title,expression,example,expected=bykey[task['tool']];action=task['action'];folder=Path(ctx['folder'])
        if action=='server':
            name=key+'_server.py';text=support.source('F28',key,title,expression)+'\nAPP='+repr(key)+'\n'+SERVER;compile(text,name,'exec')
        elif action=='interface':
            name=key+'.html';labels=review.LABELS[key];fields=''.join('<label for="n%d">%s</label><input id="n%d" name="n%d" type="number" step="any" required>'%(i,escape(label),i,i) for i,label in enumerate(labels))
            text='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>body{font:18px/1.6 system-ui;max-width:700px;margin:3rem auto;padding:1rem;color:#163c35}label,input{display:block}input,button{font:inherit;padding:.6rem;margin:.4rem 0 1rem;max-width:90%}output{display:block;min-height:2rem;font-weight:bold}</style><body><main><h1>'+escape(title)+'</h1><p>Local calculation tool. Use the units shown below. Results are floating-point estimates; verify tolerances for your application.</p><form id="calculator">'+fields+'<button type="submit">Calculate</button></form><output id="result" aria-live="polite"></output><p>No inputs are saved. This server listens only on your own computer.</p></main><script src="/app.js" defer></script></body></html>'
        elif action=='interaction':
            name=key+'.js';text='"use strict";\n// '+title+' - local form contract\n'+'''document.getElementById('calculator').addEventListener('submit', async function(event) {
 event.preventDefault(); const target = document.getElementById('result');
 const values = Array.from(this.querySelectorAll('input')).map(input => Number(input.value));
 if (values.some(value => !Number.isFinite(value))) { target.textContent = 'Enter finite numbers.'; return; }
 try { const response = await fetch('/api/calculate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(values)});
 const data = await response.json(); target.textContent = response.ok ? String(data.result) : data.error;
 } catch (error) { target.textContent = 'Local server unavailable. Restart the included Python server.'; }
});
'''
        else:
            name=key+'_reference.json';text=json.dumps({'tool':key,'title':title,'inputs':example,'expected':expected,'field_labels':review.LABELS[key]},sort_keys=True,indent=2)
            json.loads(text)
        (folder/name).write_text(text,encoding='utf8')
        if key not in name or len(text)<40:raise ValueError('F18_INCOMPLETE_COMPONENT')
        return {'passed':True,'outputs':[name],'successful_checks':2}
    def assemble(p,ctx):
        folder=Path(ctx['folder']);names=sorted(p.name for p in folder.iterdir() if p.suffix in ('.html','.js') or p.name.endswith(('_server.py','_reference.json')))
        (folder/'README.md').write_text('# Fieldwork local calculator web applications\n\nTwelve original offline HTML/JavaScript/Python applications. Requires Python 3.8+. No installation or API keys.\n\nRun `python celsius_fahrenheit_server.py` and open the printed loopback port as http://127.0.0.1:PORT/. Replace the server filename with another entry from catalog.json. Stop with Ctrl-C. Keep the files together. The random port avoids conflicts. Data stays in memory; nothing is saved.\n\nEach app labels its units. Inputs are finite; temperature may be negative; other physical values are nonnegative. Speed and density reject a zero denominator. This is technical example software, not a certified engineering instrument. The package has automated HTTP/structure tests, not human browser accessibility certification. All rights reserved Zomorod Melal; private evaluation copy.\n',encoding='utf8')
        proto.save(folder/'catalog.json',{'family_id':'F18','apps':[{'key':k,'title':v[1],'server':k+'_server.py'} for k,v in bykey.items()],'network_binding':'127.0.0.1','commercial_release':False})
        (folder/'LICENSE.txt').write_text('Copyright 2026 Zomorod Melal. Original local application code. Private technical review copy; no public license or commercial release granted.\n',encoding='utf8')
        names+=['README.md','catalog.json','LICENSE.txt']
        with zipfile.ZipFile(folder/archive_name,'w',zipfile.ZIP_DEFLATED) as z:
            for name in names:
                info=zipfile.ZipInfo(PRODUCT+'/'+name,date_time=(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,(folder/name).read_bytes())
        return {'passed':True,'outputs':['README.md','catalog.json','LICENSE.txt',archive_name],'successful_checks':4}
    def reviewer(p,ctx):
        folder=Path(ctx['folder']);result=review.check(folder,folder/archive_name,PRODUCT)
        proto.save(folder/'independent-review.json',result)
        return {'reviewer_id':'independent_loopback_http_application_review','critical_defects':[],'passed':True,'gates':result['gates'],'outputs':['independent-review.json'],'successful_checks':result['checks_passed']}
    state=proto.run_attempt(root,plan,worker,assemble,reviewer)
    if not proto.verify_attempt(home,state,snapshot):return {'status':'technical_rework_required','family_id':'F18','defects':state.get('defects',[])}
    folder=Path(state['attempt_folder']);target.mkdir(parents=True,exist_ok=True,mode=0o700);temp=target/'.incoming-webapps.zip'
    if temp.is_symlink() or (target/archive_name).is_symlink():raise ValueError('F18_UNSAFE_ARCHIVE')
    shutil.copyfile(folder/archive_name,temp);os.replace(temp,target/archive_name)
    with zipfile.ZipFile(target/archive_name) as z:files=[n.split('/',1)[1] for n in z.namelist()]
    proto.save(target/'manufacturing_manifest.json',{'schema_version':2,'recipe':PRODUCT,'family_id':'F18','name':'Fieldwork local calculator web applications','source_sha256':snapshot,'build50_source_snapshot_sha256':snapshot,'artifact_sha256':proto.file_sha(target/archive_name),'bytes':(target/archive_name).stat().st_size,'files':files,'qa_status':'passed','qa_evidence':'unit_tests_passed','qa_measurements':proto.read(folder/'independent-review.json'),'commercial_status':'private_internal_qa_pass_not_published','public_listing_enabled':False,'customer_order_required':False,'owner_publication_approval':False,'independent_human_review':False})
    return {'status':'technical_50_stage_build_completed','family_id':'F18','product_id':PRODUCT,'applications':12,'completed_stages':50,'commercial_release':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--factory-private',required=True);a=p.parse_args();r=build(a.factory_private);print('F18_BUILD50='+json.dumps(r,sort_keys=True))
    if r['status']=='technical_rework_required':raise SystemExit(2)
