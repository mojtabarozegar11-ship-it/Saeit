#!/usr/bin/env python3
"""Read-only cPanel DomainInfo docroot coverage: aggregate only, never names.

We do not claim entire-tenant backup coverage from document root coverage.
Accesses one local cPanel UAPI call and filesystem stat. No production writes.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

HOME=Path('/home/zomorod2')
BACKED_ROOTS=(HOME/'Saeit-staging',HOME/'mojplaywin.com')
ROOT_KEYS=('documentroot','document_root','document_root_path')


def _domain_records(tree):
    if isinstance(tree,list):
        for x in tree:
            yield from _domain_records(x)
    elif isinstance(tree,dict):
        roots=[tree[k] for k in ROOT_KEYS if k in tree and isinstance(tree[k],str)]
        if roots:
            yield roots[0]
        else:
            for v in tree.values():
                if isinstance(v,(list,dict)):
                    yield from _domain_records(v)


def report_from_payload(payload):
    response=payload.get('result',{}) if isinstance(payload,dict) else {}
    valid=response.get('status') in (1,'1')
    data=response.get('data') if valid else None
    roots=list(_domain_records(data))
    result={
        'classification':'MOJ_COMMERCE_V12_DOMAIN_BACKUP_COVERAGE_READ_ONLY',
        'cpanel_domaininfo_success':valid,
        'domains_with_docroot':len(roots),
        'roots_in_known_backup_scope':0,
        'roots_outside_known_backup_scope':0,
        'invalid_or_relative_docroots':0,
        'all_docroots_in_backed_roots':False,
        'complete_tenant_backup_verified':False,
        'encrypted_key_independent_escrow_verified':False,
        'payment_release_allowed':False,
        'production_modified':False
    }
    if not valid or data is None:
        return result
    for docroot in roots:
        path=Path(docroot)
        if not path.is_absolute() or '..' in path.parts:
            result['invalid_or_relative_docroots']+=1
            continue
        if any(path==r or r in path.parents for r in BACKED_ROOTS):
            result['roots_in_known_backup_scope']+=1
        else:
            result['roots_outside_known_backup_scope']+=1
    result['all_docroots_in_backed_roots']=bool(roots) and (
        result['roots_in_known_backup_scope']==len(roots))
    return result


def main():
    try:
        p=subprocess.run(
            ['uapi','--output=json','DomainInfo','domains_data'],
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            timeout=35,check=False)
        if p.returncode or len(p.stdout)>1000000:
            raise ValueError('API unavailable')
        report=report_from_payload(json.loads(p.stdout))
        print(json.dumps(report,sort_keys=True))
    except (ValueError,OSError,subprocess.TimeoutExpired,TypeError):
        print(json.dumps({'classification':'MOJ_COMMERCE_V12_DOMAININFO_UNVERIFIED',
                          'payment_release_allowed':False,'production_modified':False}))
        raise SystemExit(1)

if __name__=='__main__':
    main()
