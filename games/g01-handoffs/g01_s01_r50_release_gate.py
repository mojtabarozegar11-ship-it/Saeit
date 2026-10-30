#!/usr/bin/env python3
"""Read-only, offline Ramadan War R50 release preflight for S-01. Never deploys."""
import hashlib
import json
import re
import sys
import zipfile
from pathlib import PurePosixPath
ROOT = 'ramadan-war/'
REQUIRED = {'index.html','game.js','game.css','engine3d.js','input-guard.mjs',
            'save-validation.mjs','moj1-commerce-policy.mjs','preview-manifest.json'}
def check_archive(path):
    problems=[]
    with zipfile.ZipFile(path) as z:
        members=z.namelist()
        if len(members)!=len(set(members)): problems.append('duplicate ZIP entry')
        if any(not name.startswith(ROOT) or '..' in PurePosixPath(name).parts for name in members):
            problems.append('unexpected ZIP path')
        names={name[len(ROOT):] for name in members if name.startswith(ROOT)}
        problems.extend('missing '+name for name in sorted(REQUIRED-names))
        if problems:return problems
        if z.testzip() is not None:problems.append('ZIP CRC mismatch')
        manifest=json.loads(z.read(ROOT+'preview-manifest.json'))
        if manifest.get('payment_status')!='disabled':problems.append('payment status not disabled')
        if manifest.get('release')!='R50':problems.append('unexpected release')
        assets=manifest.get('files',{})
        if not isinstance(assets,dict) or len(assets)<20:problems.append('runtime manifest incomplete')
        for rel,meta in assets.items():
            if not isinstance(rel,str) or '..' in PurePosixPath(rel).parts or rel.startswith('/'):
                problems.append('unsafe runtime asset');continue
            if rel not in names:problems.append('missing runtime asset '+rel);continue
            data=z.read(ROOT+rel)
            if len(data)!=meta.get('bytes') or hashlib.sha256(data).hexdigest()!=meta.get('sha256'):
                problems.append('runtime asset hash mismatch '+rel)
        policy=z.read(ROOT+'moj1-commerce-policy.mjs').decode('utf-8')
        for guard in ['checkoutEnabled:false','ownerApproved:false','verifiedBackend:false','contractAddress:null']:
            if guard not in policy:problems.append('MOJ1 guard absent '+guard)
        html=z.read(ROOT+'index.html').decode('utf-8')
        if re.search(r'<script[^>]+src\\s*=\\s*["\\\']https?://',html,re.I):
            problems.append('remote executable script')
        if '<script type="module" src="./game.js"></script>' not in html:
            problems.append('game entrypoint absent')
    return problems
def main(argv):
    if len(argv)!=2:
        print('usage: python g01_s01_r50_release_gate.py <offline-preview.zip>');return 2
    try:issues=check_archive(argv[1])
    except (OSError,ValueError,zipfile.BadZipFile,KeyError,TypeError) as exc:
        print('BLOCKED: invalid release package: '+str(exc));return 1
    if issues:
        print('BLOCKED: '+'; '.join(issues));return 1
    print('READY_FOR_REVIEW: R50 CRC, runtime hashes, entrypoint, disabled MOJ1; NOT staging/live/rights approval')
    return 0
if __name__=='__main__':raise SystemExit(main(sys.argv))
