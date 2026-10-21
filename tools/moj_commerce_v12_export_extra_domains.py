#!/usr/bin/env python3
"""Stream only previously unprotected cPanel domain document roots.

Executed on the source account via pinned SSH. Reads UAPI domain metadata.
Does NOT touch MariaDB, change production files, follow symlinks, create dumps,
or expose document root names. stdout is BINARY PRIVATE DATA; pipe directly
to encrypted backup receiver, never into CI logs.
"""
from __future__ import annotations
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

HOME=Path('/home/zomorod2')
BACKED=(HOME/'Saeit-staging',HOME/'mojplaywin.com')
MARKER=b"\n-- MJWP-RECOVERY-20261017-COMPLETE-F91D7C40 --\n"
MAX_TAR_BYTES=512*1024*1024
MAX_TOTAL_KIB=256*1024


def records(tree):
    if isinstance(tree,list):
        for x in tree:
            yield from records(x)
    elif isinstance(tree,dict):
        for name in ('documentroot','document_root','document_root_path'):
            if name in tree and isinstance(tree[name],str):
                yield tree[name]
                return
        for x in tree.values():
            if isinstance(x,(list,dict)):
                yield from records(x)


def roots_for_backup(payload):
    response=payload.get('result',{}) if isinstance(payload,dict) else {}
    if response.get('status') not in (1,'1'):
        raise RuntimeError('domain API unavailable')
    domains=list(records(response.get('data')))
    if len(domains)!=4:
        raise RuntimeError('domain count drift from read-only preflight')
    outside=[]
    for item in domains:
        p=Path(item)
        if not p.is_absolute() or '..' in p.parts or p==HOME or HOME not in p.parents:
            raise RuntimeError('documentroot out of permitted account')
        if p.is_symlink() or not p.is_dir() or p.resolve(strict=True)!=p:
            raise RuntimeError('documentroot symlink or missing')
        if any(p==r or r in p.parents for r in BACKED):
            continue
        # No hidden application keys, dot-directories, shared archives or
        # .config locations may be swept up as an additional web documentroot.
        relative=p.relative_to(HOME)
        if any(part.startswith('.') for part in relative.parts):
            raise RuntimeError('non-web private path forbidden')
        if p.stat().st_uid != os.getuid():
            raise RuntimeError('foreign owner forbidden')
        outside.append(p)
    unique=sorted(set(outside),key=lambda p:(len(p.parts),str(p)))
    minimal=[]
    for p in unique:
        if not any(p==r or r in p.parents for r in minimal):
            minimal.append(p)
    if len(minimal)!=3:
        raise RuntimeError('independent root count drift from audit')
    return minimal


def execute(args,timeout=40):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                     timeout=timeout,check=False)
    if p.returncode:
        raise RuntimeError('source prerequisite command failed')
    return p.stdout


def transfer():
    raw=execute(['uapi','--output=json','DomainInfo','domains_data'])
    roots=roots_for_backup(json.loads(raw))
    size=0
    for root in roots:
        out=execute(['nice','-n','15','du','-skx','--',str(root)],timeout=35)
        size+=int(out.split()[0])
    if size<=0 or size>MAX_TOTAL_KIB:
        raise RuntimeError('unapproved site root payload size')
    rel=[str(x.relative_to(HOME)) for x in roots]
    proc=subprocess.Popen(
        ['nice','-n','15','tar','--one-file-system','-C',str(HOME),
         '-cf','-','--',*rel],stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL,bufsize=0)
    total=0
    try:
        assert proc.stdout is not None
        while True:
            chunk=proc.stdout.read(131072)
            if not chunk:
                break
            total+=len(chunk)
            if total>MAX_TAR_BYTES:
                raise RuntimeError('archive exceeded strict maximum')
            sys.stdout.buffer.write(chunk)
        if proc.wait(timeout=60)!=0:
            raise RuntimeError('source tar failed, never mark complete')
        sys.stdout.buffer.write(MARKER)
        sys.stdout.buffer.flush()
        print(json.dumps({
            'classification':'MOJ_COMMERCE_V12_EXTRA_DOMAIN_SOURCE_STREAM',
            'source_roots':3,'stream_bytes':total,
            'source_read_only':True,'site_and_db_writes':False,
            'release_permitted':False},sort_keys=True),file=sys.stderr,flush=True)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


if __name__=='__main__':
    try:
        if sys.argv[1:]!=['export']:
            raise RuntimeError('unsupported mode')
        transfer()
    except Exception:
        print('EXTRA_DOMAIN_SOURCE_BACKUP_FAILED_NO_RELEASE',file=sys.stderr)
        raise SystemExit(1)
