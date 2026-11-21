#!/usr/bin/env python3
"""Deterministic, secret-free offline handoff archives, verified after creation."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parent.parent
OUTPUT=Path('/mnt/data')
FILES=[
    *sorted(str(p.relative_to(ROOT)) for p in (ROOT/'content/zomorod-business').glob('*') if p.is_file()),
    *sorted(str(p.relative_to(ROOT)) for p in (ROOT/'scripts').glob('*.py')),
    *sorted(str(p.relative_to(ROOT)) for p in (ROOT/'scripts').glob('*.php')),
    *sorted(str(p.relative_to(ROOT)) for p in (ROOT/'docs').glob('*.md')),
    '.github/workflows/zomorod-erp-offline-validation.yml',
    'OFFLINE_QA_REPORT.json',
]

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def tar_info(name:str,b:bytes):
    i=tarfile.TarInfo('zomorod-erp-offline-v6-verified/'+name)
    i.size=len(b);i.mode=0o644;i.uid=i.gid=i.mtime=0
    return i

def build():
    payload={}
    for p in FILES:
        file=ROOT/p
        if file.is_symlink() or not file.is_file():raise ValueError('Invalid source '+p)
        payload[p]=file.read_bytes()
    report=json.loads(payload['OFFLINE_QA_REPORT.json'])
    manifest={
      'package':'zomorod-erp-offline-v6-verified',
      'status':'DEVELOPMENT_ONLY_NOT_PRODUCTION_DEPLOYABLE',
      'generated_source':'conversation_offline_workspace',
      'production_data_included':False,'secret_material_included':False,
      'live_website_modified':False,'one_hour_scheduler_created':False,
      'offline_checks_available_here':report['offline_checks_available_here'],
      'php_database_tests':report['php_sqlite_business_tests'],
      'files':[{'path':n,'bytes':len(b),'sha256':sha(b)} for n,b in sorted(payload.items())],
      'required_gates':['PHP PDO_SQLite functional regression PASS',
          'full statutory payroll/tax/treasury and accounting review',
          'cross-site authenticated command bridge and server-only extensions reconciliation',
          'complete agricultural/LIMS/MES functional acceptance',
          'independent security and disaster-recovery tests',
          'owner signoff before deployment or one-hour automation'],
    }
    payload['MANIFEST.json']=(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    name='zomorod-erp-offline-v6-verified'
    zippath=OUTPUT/(name+'.zip')
    tarpath=OUTPUT/(name+'.tar.gz')
    with zipfile.ZipFile(zippath,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p,b in sorted(payload.items()):
            item=zipfile.ZipInfo(name+'/'+p,date_time=(2020,1,1,0,0,0))
            item.external_attr=0o100644<<16
            item.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(item,b,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with open(tarpath,'wb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0,compresslevel=9) as gz:
            with tarfile.open(fileobj=gz,mode='w',format=tarfile.PAX_FORMAT) as tar:
                for p,b in sorted(payload.items()):tar.addfile(tar_info(p,b),io.BytesIO(b))
    for path in [zippath,tarpath]:
        if path.suffix=='.zip':
            with zipfile.ZipFile(path) as z:
                rootname=name+'/'
                extracted={p.removeprefix(rootname):z.read(p) for p in z.namelist()}
        else:
            with tarfile.open(path,'r:gz') as tar:
                rootname=name+'/'
                extracted={p.name.removeprefix(rootname):tar.extractfile(p).read() for p in tar.getmembers()}
        expected={d['path']:d for d in manifest['files']}
        assert len(extracted)==len(payload)
        for p,d in expected.items():
            assert sha(extracted[p])==d['sha256'] and len(extracted[p])==d['bytes']
        assert extracted['MANIFEST.json']==payload['MANIFEST.json']
    print('PACKAGE_VALIDATION=PASS')
    print('FILES='+str(len(payload)))
    print('PHP_SQLITE_FUNCTIONAL_TESTS='+manifest['php_database_tests'])
    print('PRODUCTION_READY=NO')
    for path in [zippath,tarpath]:print(path, path.stat().st_size,sha(path.read_bytes()))

if __name__=='__main__':build()
