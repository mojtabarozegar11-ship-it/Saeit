#!/usr/bin/env python3
"""Guarded, reversible addition of two already-live Zomorod guide URLs to the public sitemap."""
import fcntl,hashlib,json,os,re,sys,tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

HOME=Path('/home/zomorod2')
ROOT=HOME/'public_html'
SITEMAP=ROOT/'sitemap.xml'
LOCK=HOME/'.locks/zm-guide-sitemap-20261025b.lock'
BACKUP=HOME/'.backups/zm-guide-sitemap-20261025b'
URLS=(
 'https://zomorodmelal.ir/resources/20261025b/cold-chain-acceptance/',
 'https://zomorodmelal.ir/resources/20261025b/supplier-technical-comparison/',
)
def sha(b):return hashlib.sha256(b).hexdigest()
def check_path(p,kind='file'):
    if not ROOT.is_dir() or ROOT.is_symlink() or not str(p).startswith(str(ROOT)+os.sep):
        raise RuntimeError('UNSAFE_ROOT')
    cur=p
    while cur!=ROOT:
        if cur.is_symlink():raise RuntimeError('SYMLINK_PATH')
        cur=cur.parent
    if kind=='file' and not p.is_file():raise RuntimeError('MISSING_FILE:'+str(p))
    return p
def atomic(p,data):
    fd,tmp=tempfile.mkstemp(prefix='.zm-sitemap-',dir=str(p.parent))
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,p.stat().st_mode & 0o777)
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def apply(run):
    for slug in ('cold-chain-acceptance','supplier-technical-comparison'):
        check_path(ROOT/'resources/20261025b'/slug/'index.html')
    check_path(SITEMAP)
    before=SITEMAP.read_bytes()
    tree=ET.fromstring(before)
    if not tree.tag.endswith('urlset'):raise RuntimeError('INVALID_SITEMAP_ROOT')
    locs=[e.text for e in tree.iter() if e.tag.endswith('loc')]
    if len(locs)!=len(set(locs)):raise RuntimeError('EXISTING_DUPLICATE_LOC')
    missing=[u for u in URLS if u not in locs]
    if not missing:
        print('GUIDE_SITEMAP_ALREADY_CORRECT_NO_CHANGE');return
    s=before.decode('utf8')
    if s.count('</urlset>')!=1:raise RuntimeError('UNEXPECTED_XML_END')
    addition=''.join('  <url><loc>'+u+'</loc></url>\n' for u in missing)
    after=s.replace('</urlset>',addition+'</urlset>',1).encode('utf8')
    nextloc=[e.text for e in ET.fromstring(after).iter() if e.tag.endswith('loc')]
    if len(nextloc)!=len(locs)+len(missing) or any(nextloc.count(u)!=1 for u in URLS):
        raise RuntimeError('POSTPATCH_XML_INVALID')
    bdir=BACKUP/run
    if bdir.exists():raise RuntimeError('BACKUP_ALREADY_EXISTS')
    bdir.mkdir(mode=0o700,parents=True)
    (bdir/'sitemap.before').write_bytes(before)
    (bdir/'manifest.json').write_text(json.dumps({'before':sha(before),'after':sha(after),'urls':missing}),encoding='utf8')
    if SITEMAP.read_bytes()!=before:raise RuntimeError('CONCURRENT_SITEMAP_CHANGE')
    atomic(SITEMAP,after)
    print('GUIDE_SITEMAP_URLS_ADDED',len(missing))
    for u in missing:print('SITEMAP_NEW_URL',u)
def rollback(run):
    bdir=BACKUP/run
    if not bdir.exists():
        print('NO_NEW_SITEMAP_CHANGE_TO_ROLLBACK');return
    m=json.loads((bdir/'manifest.json').read_text())
    old=(bdir/'sitemap.before').read_bytes()
    if sha(old)!=m['before']:raise RuntimeError('BACKUP_HASH_MISMATCH')
    now=SITEMAP.read_bytes()
    if sha(now)==m['before']:
        print('SITEMAP_ALREADY_ROLLED_BACK');return
    if sha(now)!=m['after']:raise RuntimeError('CONCURRENT_CHANGE_ROLLBACK_REFUSED')
    atomic(SITEMAP,old)
    print('SITEMAP_RESTORED_TO_PREVIOUS_BYTES')
def main():
    if len(sys.argv)!=3 or sys.argv[1] not in ('apply','rollback') or not re.fullmatch(r'[0-9]{6,20}',sys.argv[2]):
        raise SystemExit('usage: apply|rollback numeric_run_id')
    LOCK.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    BACKUP.mkdir(mode=0o700,parents=True,exist_ok=True)
    with LOCK.open('a+b') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        (apply if sys.argv[1]=='apply' else rollback)(sys.argv[2])
if __name__=='__main__':main()
