#!/usr/bin/env python3
"""Read-only cPanel DomainInfo docroot coverage: aggregate only, never names.

We do not claim entire-tenant backup coverage from document root coverage.
Accesses one local cPanel UAPI call and filesystem stat. No production writes.
"""
from __future__ import annotations
import json
import os
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


def estimate_missing_backup_roots(domain_docroots):
    """Bounded low-priority read-only size inventory; no path output."""
    outside=[]
    for root_string in domain_docroots:
        p=Path(root_string)
        if not p.is_absolute() or '..' in p.parts or (p!=HOME and HOME not in p.parents):
            continue
        if any(p==r or r in p.parents for r in BACKED_ROOTS):
            continue
        if p.is_symlink() or not p.is_dir():
            continue
        outside.append(p)
    minimum=[]
    for p in sorted(set(outside),key=lambda p:(len(p.parts),str(p))):
        if not any(p==r or r in p.parents for r in minimum):
            minimum.append(p)
    summary={'minimal_additional_backup_roots':len(minimum),
             'estimated_bytes':0,'complete_size_estimate':True,
             'copy_or_snapshot_performed':False}
    for root in minimum:
        try:
            run=subprocess.run(['nice','-n','15','du','-skx','--',str(root)],
                               capture_output=True,timeout=25,check=False)
            if run.returncode:
                raise ValueError('du_unavailable')
            size=int(run.stdout.split()[0])
            if size<0:
                raise ValueError('invalid_size')
            summary['estimated_bytes']+=size*1024
        except (OSError,ValueError,IndexError,subprocess.TimeoutExpired):
            summary['complete_size_estimate']=False
    return summary


def inspect_live_symlinks(domain_docroots):
    """Summarize LIVE metadata only; a current symlink is not a backup attestation."""
    outside=[]
    for root_string in domain_docroots:
        p=Path(root_string)
        if not p.is_absolute() or '..' in p.parts:
            continue
        if not any(p==r or r in p.parents for r in BACKED_ROOTS):
            outside.append(p)
    counts={'inspected_live_entries':0,'live_absolute_links':0,
            'live_links_to_unbacked_domain_root':0,
            'live_links_to_other_account_path':0,
            'live_links_to_unbacked_application_source':0,
            'live_links_to_private_dot_directory':0,
            'live_links_to_other_unbacked_account_path':0,
            'live_links_to_system_or_elsewhere':0,
            'inventory_complete':True,
            'exact_archive_link_match_verified':False}
    def errors(_):
        counts['inventory_complete']=False
    try:
        for root in BACKED_ROOTS:
            if root.is_symlink() or not root.is_dir():
                counts['inventory_complete']=False
                continue
            for current,dirs,files in os.walk(root,topdown=True,followlinks=False,onerror=errors):
                for name in dirs+files:
                    counts['inspected_live_entries']+=1
                    if counts['inspected_live_entries']>150000:
                        counts['inventory_complete']=False
                        return counts
                    p=Path(current)/name
                    if not p.is_symlink():
                        continue
                    target=os.readlink(p)
                    if not target.startswith('/'):
                        continue
                    counts['live_absolute_links']+=1
                    link=Path(target)
                    if any(link==r or r in link.parents for r in outside):
                        counts['live_links_to_unbacked_domain_root']+=1
                    elif link==HOME or HOME in link.parents:
                        counts['live_links_to_other_account_path']+=1
                        live_source=HOME/'Saeit'
                        if link==live_source or live_source in link.parents:
                            counts['live_links_to_unbacked_application_source']+=1
                        elif any(part.startswith('.') for part in link.relative_to(HOME).parts):
                            counts['live_links_to_private_dot_directory']+=1
                        else:
                            counts['live_links_to_other_unbacked_account_path']+=1
                    else:
                        counts['live_links_to_system_or_elsewhere']+=1
    except (OSError,ValueError):
        counts['inventory_complete']=False
    return counts


def main():
    try:
        p=subprocess.run(
            ['uapi','--output=json','DomainInfo','domains_data'],
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            timeout=35,check=False)
        if p.returncode or len(p.stdout)>1000000:
            raise ValueError('API unavailable')
        payload=json.loads(p.stdout)
        report=report_from_payload(payload)
        if report['cpanel_domaininfo_success']:
            domain_roots=list(_domain_records(payload.get('result',{}).get('data')))
            report['live_link_inventory']=inspect_live_symlinks(domain_roots)
            report['additional_site_backup_size']=estimate_missing_backup_roots(domain_roots)
        print(json.dumps(report,sort_keys=True))
    except (ValueError,OSError,subprocess.TimeoutExpired,TypeError):
        print(json.dumps({'classification':'MOJ_COMMERCE_V12_DOMAININFO_UNVERIFIED',
                          'payment_release_allowed':False,'production_modified':False}))
        raise SystemExit(1)

if __name__=='__main__':
    main()
