#!/usr/bin/env python3
"""Fail-closed offline source gate for AE-2026-001. No network or VPS access.
Usage: python ae_wdi_original_response_gate_C130.py employment.json value_added.json
Only original World Bank API [metadata, records] JSON is acceptable.
"""
import argparse, hashlib, json, pathlib, sys
SERIES={'SL.AGR.EMPL.ZS':'agricultural_employment_share_pct','NV.AGR.TOTL.ZS':'agricultural_value_added_share_pct_gdp'}
YEARS={'2023','2024'}

def validate(path, indicator):
    raw=pathlib.Path(path).read_bytes()
    parsed=json.loads(raw)
    if not isinstance(parsed,list) or len(parsed)!=2 or not isinstance(parsed[0],dict) or not isinstance(parsed[1],list):
        raise ValueError('Expected original World Bank API [metadata, records] JSON')
    meta,records=parsed
    if meta.get('page')!=1 or meta.get('pages')!=1 or meta.get('total')!=len(records):
        raise ValueError('Incomplete or inconsistent pagination; archive all pages')
    found={}
    for item in records:
        if not isinstance(item,dict) or item.get('indicator',{}).get('id')!=indicator:
            raise ValueError('Wrong or missing indicator')
        if item.get('countryiso3code')!='IND' or item.get('country',{}).get('id')!='IN':
            raise ValueError('Country must be India (IND/IN)')
        y=str(item.get('date'))
        if y not in YEARS: continue
        if y in found: raise ValueError('Duplicate country/indicator/year')
        v=item.get('value')
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not 0<=v<=100:
            raise ValueError('Missing/non-numeric/out-of-range WDI share')
        found[y]=float(v)
    if set(found)!=YEARS: raise ValueError('Required 2023 and 2024 observations absent')
    return {'indicator':indicator,'label':SERIES[indicator],'values':found,
            'source_sha256':hashlib.sha256(raw).hexdigest(),'source_bytes':len(raw)}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('employment_json');p.add_argument('value_added_json')
    a=p.parse_args(argv)
    e=validate(a.employment_json,'SL.AGR.EMPL.ZS')
    v=validate(a.value_added_json,'NV.AGR.TOTL.ZS')
    result={'status':'RAW_WDI_RECONCILED_NOT_ILOSTAT_VERIFIED','country':'IND','series':[e,v],'years':{}}
    for y in sorted(YEARS):
        x=e['values'][y]; z=v['values'][y]
        if z==0: raise ValueError('Value-added share denominator zero')
        result['years'][y]={'employment_share_pct':x,'value_added_share_pct_gdp':z,
                            'gap_percentage_points':x-z,'share_ratio_not_productivity':x/z}
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,TypeError,json.JSONDecodeError) as exc:
        print('BLOCKED: '+str(exc),file=sys.stderr);sys.exit(2)
