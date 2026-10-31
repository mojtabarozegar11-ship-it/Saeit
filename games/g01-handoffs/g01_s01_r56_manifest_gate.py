#!/usr/bin/env python3
"""G->S read-only R56 integrity gate; NEVER deploys or writes to host."""
import hashlib, json, stat, sys, zipfile
from pathlib import Path, PurePosixPath

def verify(path):
    if path.stat().st_size > 30_000_000:
        return ['ARCHIVE_TOO_LARGE']
    with zipfile.ZipFile(path) as z:
        entries=z.infolist()
        names=[e.filename for e in entries]
        if len(names)!=len(set(names)):return ['DUPLICATE_ENTRY']
        if sum(e.file_size for e in entries)>80_000_000:return ['UNCOMPRESSED_TOO_LARGE']
        for e in entries:
            n=e.filename
            if not n.startswith('ramadan-war/') or '..' in PurePosixPath(n).parts or '\\' in n or stat.S_IFMT(e.external_attr>>16)==stat.S_IFLNK:
                return ['UNSAFE_ENTRY']
        if z.testzip() is not None:return ['ZIP_CRC_FAIL']
        data={e.filename[12:]:z.read(e) for e in entries if not e.is_dir()}
    errors=[]
    for n in ('game.js','index.html','preview-manifest.json','R56-MANIFEST-SHA256.json','moj1-commerce-policy.mjs'):
        if n not in data:errors.append('MISSING:'+n)
    if errors:return errors
    runtime=json.loads(data['preview-manifest.json'])
    full=json.loads(data['R56-MANIFEST-SHA256.json'])
    if runtime.get('release')!='R56' or full.get('release')!='R56':errors.append('STALE_RELEASE')
    if runtime.get('payment_status')!='disabled' or full.get('moj1_live_payments') is not False or full.get('factory_hold') is not True:errors.append('POLICY_MISMATCH')
    for manifest in (runtime,full):
        for n,v in manifest['files'].items():
            b=data.get(n)
            if b is None:errors.append('MISSING:'+n)
            elif len(b)!=v['bytes'] or hashlib.sha256(b).hexdigest()!=v['sha256']:errors.append('HASH_MISMATCH:'+n)
    if set(data)-{'R56-MANIFEST-SHA256.json'}!=set(full['files']):errors.append('UNTRACKED_FILE')
    policy=data['moj1-commerce-policy.mjs'].decode('utf-8','replace')
    for x in ('contractAddress:null','ownerApproved:false','checkoutEnabled:false','verifiedBackend:false'):
        if x not in policy:errors.append('MOJ1_NOT_DISABLED:'+x)
    return sorted(set(errors))

if __name__=='__main__':
    issues=verify(Path(sys.argv[1]))
    print('BLOCKED: '+', '.join(issues) if issues else 'PASS: static integrity only; browser and release gates still required')
    raise SystemExit(2 if issues else 0)
