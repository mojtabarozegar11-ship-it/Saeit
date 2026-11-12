#!/usr/bin/env python3
"""One-field, hash-pinned production correction of NEXUS archived-home footer URL.

Only /home/zomorod2/public_html/index.html may be changed. Never touch
internal pages, global CSS, .htaccess, PHP, payment or original archive.
"""
from __future__ import annotations
import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
from pathlib import Path

SITE=Path('/home/zomorod2/public_html')
HOME=SITE/'index.html'
ARCHIVE=SITE/'site-heritage/home-before-nexus-20261112/index.html'
BACKUPS=Path('/home/zomorod2/.backups/zomorod-nexus-footer-link-20261112')
EXPECTED='f2fadc049f8315927e7d98f0849149b7f88249773b9ca549ed6799f2e3c86f60'
ARCHIVED='99e9c38cd20aaf400a3c68c2064211dc48d4ff0e518ee4815061ea0ca2626edc'
OLD=b'href="/site-heritage/home-before-nexus-20261112/"'
NEW=b'href="/site-heritage/home-before-nexus-20261112/index.html"'
PROTECTED=(
 'agriculture/index.html','research/index.html','industry/index.html',
 'company/index.html','services/index.html','contact/index.html',
 'store/index.php','sitemap.xml','.htaccess',
 'games/index.html','apps/index.html',
)

def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def transform(raw:bytes)->bytes:
    if digest(raw)!=EXPECTED or raw.count(OLD)!=1 or NEW in raw:
        raise RuntimeError('Unexpected homepage version or footer; fail closed')
    if b'<body class="nexus-home">' not in raw:
        raise RuntimeError('Homepage is not NEXUS')
    output=raw.replace(OLD,NEW,1)
    if output.replace(NEW,OLD,1)!=raw:
        raise RuntimeError('Unexpected collateral edit')
    return output

def ensure():
    if pwd.getpwuid(os.geteuid()).pw_name!='zomorod2':
        raise RuntimeError('Unexpected host identity')
    if not SITE.is_dir() or SITE.is_symlink() or BACKUPS.is_symlink():
        raise RuntimeError('Unexpected production directory')
    for path in (HOME,ARCHIVE):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError('Protected source missing or symbolic link')
    if digest(ARCHIVE.read_bytes())!=ARCHIVED:
        raise RuntimeError('Verified original archive changed')
    if not BACKUPS.parent.is_dir() or BACKUPS.parent.is_symlink():
        raise RuntimeError('Private backup parent unavailable')

def fingerprints():
    out={}
    for relative in PROTECTED:
        f=SITE/relative
        if f.is_file():
            if f.is_symlink():raise RuntimeError('Protected symbolic link')
            out[relative]=digest(f.read_bytes())
    if len(out)<8:raise RuntimeError('Insufficient protected internal files')
    return out

def atomic(path:Path,raw:bytes,mode:int):
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.nexus-footer-',delete=False) as f:
            tmp=Path(f.name)
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,mode)
        os.replace(tmp,path)
    finally:
        if tmp is not None and tmp.exists():tmp.unlink()

def release_dir(run:str)->Path:
    if not re.fullmatch(r'footer-[0-9]{1,20}',run):
        raise RuntimeError('Invalid release id')
    return BACKUPS/run

def apply(run:str):
    ensure()
    before=HOME.read_bytes()
    after=transform(before)
    saved=fingerprints()
    folder=release_dir(run)
    if folder.exists() or folder.is_symlink():
        raise RuntimeError('Release backup already exists')
    folder.mkdir(parents=True,mode=0o700)
    old_mode=stat.S_IMODE(HOME.stat().st_mode)
    atomic(folder/'index.before.html',before,0o600)
    if digest((folder/'index.before.html').read_bytes())!=EXPECTED:
        raise RuntimeError('Backup checksum mismatch')
    manifest={'old':digest(before),'new':digest(after),'mode':old_mode,'protected':saved}
    (folder/'manifest.json').write_text(json.dumps(manifest,sort_keys=True),encoding='utf-8')
    if digest(HOME.read_bytes())!=EXPECTED:
        raise RuntimeError('Concurrent change; abort')
    try:
        atomic(HOME,after,old_mode)
        assert digest(HOME.read_bytes())==manifest['new']
        assert fingerprints()==saved
        assert digest(ARCHIVE.read_bytes())==ARCHIVED
    except BaseException:
        if digest(HOME.read_bytes())==manifest['new']:
            atomic(HOME,before,old_mode)
        raise
    print('NEXUS_ARCHIVE_FOOTER_APPLIED=YES')
    print('NEXUS_INNER_FILES_UNCHANGED=YES')
    print('NEXUS_NEW_HOME_SHA256='+manifest['new'])

def verify(run:str):
    ensure()
    folder=release_dir(run)
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if digest((folder/'index.before.html').read_bytes())!=manifest['old']:
        raise RuntimeError('Private backup mismatch')
    if digest(HOME.read_bytes())!=manifest['new']:
        raise RuntimeError('Homepage mismatch')
    if fingerprints()!=manifest['protected']:
        raise RuntimeError('Internal pages modified')
    if NEW not in HOME.read_bytes():
        raise RuntimeError('Archive footer target not fixed')
    print('NEXUS_ARCHIVE_FOOTER_VERIFIED=YES')

def rollback(run:str):
    ensure()
    folder=release_dir(run)
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    before=(folder/'index.before.html').read_bytes()
    if digest(before)!=manifest['old']:
        raise RuntimeError('Private backup mismatch')
    now=digest(HOME.read_bytes())
    if now==manifest['old']:
        print('NEXUS_ARCHIVE_FOOTER_ALREADY_RESTORED=YES')
        return
    if now!=manifest['new']:
        raise RuntimeError('Unexpected concurrent page; abort rollback')
    atomic(HOME,before,manifest['mode'])
    assert digest(HOME.read_bytes())==manifest['old']
    assert fingerprints()==manifest['protected']
    print('NEXUS_ARCHIVE_FOOTER_ROLLBACK=YES')

def selftest():
    sample=b'<body class="nexus-home">' + OLD + b'</body>'
    # Test reversible one-field substitution separately from pinned SHA preflight.
    modified=sample.replace(OLD,NEW)
    assert modified.replace(NEW,OLD)==sample
    assert modified.count(NEW)==1 and modified.count(OLD)==0
    print('NEXUS_ARCHIVE_FOOTER_SELFTEST=PASS')

if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':
        selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ('apply','verify','rollback'):
        {'apply':apply,'verify':verify,'rollback':rollback}[sys.argv[1]](sys.argv[2])
    else:
        raise SystemExit('Usage: selftest | apply RUN | verify RUN | rollback RUN')
