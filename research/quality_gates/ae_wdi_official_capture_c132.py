#!/usr/bin/env python3
"""AE-2026-001 official World Bank indicator raw-response capture. Offline, no server side effects.
Requires explicit --out directory; rejects non-World Bank origin redirects; stores exact bytes and SHA256.
Does NOT imply ILOSTAT independently sourced, or make causal claims.
"""
import argparse, hashlib, json, pathlib, urllib.request, urllib.parse, datetime, sys
INDICATORS=('SL.AGR.EMPL.ZS','NV.AGR.TOTL.ZS')

def validate_response(raw, code, indicator):
    obj=json.loads(raw)
    if not isinstance(obj,list) or len(obj)!=2 or not isinstance(obj[0],dict) or not isinstance(obj[1],list): raise ValueError('unexpected World Bank API envelope')
    m,rows=obj
    if m.get('pages')!=1 or m.get('total',0)<1: raise ValueError('pagination/incomplete response')
    selected={}
    for r in rows:
        if r.get('countryiso3code')!=code or r.get('indicator',{}).get('id')!=indicator: raise ValueError('wrong country or indicator')
        if r.get('date') in ('2023','2024'):
            if r.get('date') in selected: raise ValueError('duplicate year')
            if not isinstance(r.get('value'),(float,int)): raise ValueError('missing/non-numeric value')
            selected[r['date']]=r['value']
    if set(selected)!={'2023','2024'}: raise ValueError('required years absent')
    return selected,m.get('lastupdated')

def capture(out, fetch):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    manifests=[]
    for ind in INDICATORS:
        url=f'https://api.worldbank.org/v2/country/IND/indicator/{ind}?format=json&date=2023%3A2024&per_page=100'
        raw,final_url=fetch(url)
        p=urllib.parse.urlparse(final_url)
        if p.scheme!='https' or p.hostname!='api.worldbank.org': raise ValueError('unexpected redirect origin')
        vals,updated=validate_response(raw,'IND',ind)
        name=f'IND_{ind.replace(".","_")}_2023_2024.json'
        (out/name).write_bytes(raw)
        manifests.append({'file':name,'source_url':url,'final_url':final_url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'values':vals,'provider_lastupdated':updated})
    (out/'capture_manifest.json').write_text(json.dumps({'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'country':'IND','indicators':manifests,'ILOSTAT_independent_verification':'NOT_DONE'},indent=2),encoding='utf-8')
    return manifests

def live_fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'AE-2026-001-source-capture/1.0'})
    with urllib.request.urlopen(req,timeout=25) as resp: return resp.read(),resp.geturl()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    try:print(json.dumps(capture(args.out,live_fetch),indent=2))
    except Exception as e: print('BLOCKED: official capture failed: '+str(e),file=sys.stderr);sys.exit(2)
