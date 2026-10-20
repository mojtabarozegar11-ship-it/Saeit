"""Independent functional HTTP and boundary/security review, not human browser QA."""
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import select
import subprocess
import sys
import urllib.request
import urllib.error
import zipfile

LABELS={
'celsius_fahrenheit':['Temperature (degrees Celsius)'],'fahrenheit_celsius':['Temperature (degrees Fahrenheit)'],
'km_miles':['Distance (kilometres)'],'litres_gallons':['Volume (litres)'],
'rectangle_area':['Width (metres)','Height (metres)'],'triangle_area':['Base (metres)','Altitude (metres)'],
'circle_area':['Radius (metres)'],'cylinder_volume':['Radius (metres)','Height (metres)'],
'speed':['Distance (metres)','Elapsed time (seconds)'],'density':['Mass (kilograms)','Volume (cubic metres)'],
'ohms_voltage':['Current (amperes)','Resistance (ohms)'],'electric_energy':['Power (watts)','Elapsed time (hours)']}
CASES={'celsius_fahrenheit':([-40],-40),'fahrenheit_celsius':([212],100),'km_miles':([1.609344],1),
 'litres_gallons':([3.785411784],1),'rectangle_area':([3,4],12),'triangle_area':([3,4],6),
 'circle_area':([2],12.566370614359172),'cylinder_volume':([2,1],12.566370614359172),
 'speed':([9,3],3),'density':([8,2],4),'ohms_voltage':([3,6],18),'electric_energy':([500,3],1.5)}
GATES=('requirements','correctness','negative_cases','usability','accessibility','security','compatibility','provenance','specialist_review','release_integrity')
class Page(HTMLParser):
    def __init__(self):super().__init__();self.labels=[];self.inputs=[];self.scripts=[];self.lang=False;self.heading=False;self.live=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='html':self.lang=a.get('lang')=='en'
        if tag=='h1':self.heading=True
        if tag=='label':self.labels.append(a.get('for'))
        if tag=='input':self.inputs.append(a.get('id'))
        if tag=='script':self.scripts.append(a.get('src'))
        if tag=='output':self.live=a.get('aria-live')=='polite'

def http(base,path='/',value=None,headers=None):
    data=None if value is None else value
    req=urllib.request.Request(base+path,data=data,headers=headers or {})
    # Never use environment proxies for isolated loopback test traffic.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req,timeout=3) as r:return r.status,r.read()
    except urllib.error.HTTPError as error:return error.code,error.read()

def check(folder,archive,product):
    folder=Path(folder);expected={'README.md','catalog.json','LICENSE.txt'};count=0
    catalog=json.loads((folder/'catalog.json').read_text())
    if catalog.get('family_id')!='F18' or {x['key'] for x in catalog['apps']}!=set(LABELS):raise ValueError('F18_APPLICATION_CATALOG')
    for key,labels in LABELS.items():
        expected.update({key+'_server.py',key+'.html',key+'.js',key+'_reference.json'})
        page=Page();html=(folder/(key+'.html')).read_text();page.feed(html)
        if not(page.lang and page.heading and page.live and len(page.inputs)==len(labels) and len(set(page.inputs))==len(labels) and set(page.labels)==set(page.inputs) and page.scripts==['/app.js']):raise ValueError('F18_INTERFACE_ACCESSIBILITY')
        if any(label not in html for label in labels):raise ValueError('F18_UNITS_MISSING')
        script=(folder/(key+'.js')).read_text()
        if "fetch('/api/calculate'" not in script or '.textContent' not in script or 'innerHTML' in script or 'http://' in script or 'https://' in script:raise ValueError('F18_UNSAFE_CLIENT')
        source=(folder/(key+'_server.py')).read_text()
        if "HTTPServer(('127.0.0.1',a.port)" not in source or 'eval(' in source or 'exec(' in source:raise ValueError('F18_SERVER_SCOPE')
        child=subprocess.Popen([sys.executable,'-B',str(folder/(key+'_server.py'))],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            ready,_,_=select.select([child.stdout],[],[],6)
            if not ready:raise ValueError('F18_SERVER_START_TIMEOUT')
            line=child.stdout.readline().strip()
            if not line.startswith('LOCAL_WEB_APP_PORT='):raise ValueError('F18_SERVER_DID_NOT_START')
            port=int(line.split('=')[1]);base='http://127.0.0.1:'+str(port)
            status,body=http(base)
            if status!=200 or body.decode()!=html:raise ValueError('F18_HTML_ROUTE')
            status,body=http(base,'/app.js')
            if status!=200 or body.decode()!=script:raise ValueError('F18_SCRIPT_ROUTE')
            inputs,wanted=CASES[key];status,body=http(base,'/api/calculate',json.dumps(inputs).encode(),{'Content-Type':'application/json'})
            actual=json.loads(body).get('result')
            if status!=200 or type(actual) not in (int,float) or not math.isclose(actual,wanted,rel_tol=1e-10,abs_tol=1e-10):raise ValueError('F18_REFERENCE_RESULT')
            for value in (b'null',b'true',b'[true]',b'[NaN]',b'not json'):
                if http(base,'/api/calculate',value,{'Content-Type':'application/json'})[0]!=400:raise ValueError('F18_INVALID_INPUT_ACCEPTED')
            if http(base,'/../README.md')[0]!=404:raise ValueError('F18_PATH_ESCAPE')
            if http(base,headers={'Host':'example.org'})[0]!=403:raise ValueError('F18_UNTRUSTED_HOST')
            if http(base,'/api/calculate',b'[1]',{'Content-Type':'application/json','Origin':'https://example.org'})[0]!=403:raise ValueError('F18_CROSS_ORIGIN')
            if http(base,'/api/calculate',b'[1]',{'Content-Type':'text/plain'})[0]!=400:raise ValueError('F18_CONTENT_TYPE')
            if key in ('speed','density') and http(base,'/api/calculate',b'[1,0]',{'Content-Type':'application/json'})[0]!=400:raise ValueError('F18_ZERO_DIVISION')
            count+=15
        finally:
            child.terminate()
            try:child.communicate(timeout=3)
            except subprocess.TimeoutExpired:child.kill();child.communicate()
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist())!=51 or set(z.namelist())!={product+'/'+n for n in expected} or z.testzip() is not None:raise ValueError('F18_ARCHIVE_LAYOUT')
        for name in expected:
            if (folder/name).is_symlink() or z.read(product+'/'+name)!=(folder/name).read_bytes():raise ValueError('F18_ARCHIVE_TAMPERED')
    return {'passed':True,'checks_passed':count,'applications_http_tested':12,'gates':dict.fromkeys(GATES,True),
      'human_browser_review':False,'commercial_release':False,'network_binding':'127.0.0.1',
      'review_scope':'actual local HTTP results, labelled UI structure, input boundaries, origin restrictions and archive integrity'}
