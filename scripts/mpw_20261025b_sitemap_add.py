#!/usr/bin/env python3
"""Safely register six already-live MojPlayWin educational URLs in its PHP-generated sitemap.
Only the known sitemap PHP include may change. No site content, accounts or checkout is modified.
"""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,tempfile

HOME=Path('/home/zomorod2')
SITE=HOME/'mojplaywin.com/design-preview-20261017/_mpw_sitemap_three_indexable_20261017.php'
BACKUPS=HOME/'.mpw-learning-b-sitemap-20261025'
MARKER='// 2026-10-25: verified 13 revenue URLs return 404; do not append to sitemap.'
SLUGS=('chess-error-review','taniya-creative-retelling','atelier-accessibility-acceptance',
       'browser-game-retention-diagnostics','digital-product-license-check','research-data-audit-trail')
SIGNATURE='// 2026-10-25: verified canonical MPW learning resources, isolated sitemap registration'
def sha(b):return hashlib.sha256(b).hexdigest()
def guard():
    root=HOME/'mojplaywin.com'
    if root.is_symlink() or not root.is_dir() or SITE.is_symlink() or SITE.parent.is_symlink() or not SITE.is_file():
        raise RuntimeError('UNTRUSTED_SITEMAP_SOURCE')
    if not (root/'.htaccess').is_file():raise RuntimeError('MAIN_DOMAIN_IDENTITY_NOT_VERIFIED')
    for slug in SLUGS:
        page=root/'mpw-learning/20261025b'/slug/'index.html'
        if page.is_symlink() or not page.is_file():raise RuntimeError('REQUIRED_PAGE_MISSING:'+slug)
def patch(b):
    s=b.decode('utf8')
    if SIGNATURE in s:
        print('MPW_SITEMAP_GUIDES_ALREADY_REGISTERED');return b
    if s.count(MARKER)!=1:raise RuntimeError('SITEMAP_ANCHOR_DRIFT')
    paths=",".join("'"+'/mpw-learning/20261025b/'+slug+"/'" for slug in SLUGS)
    addition=SIGNATURE+"\n$paths = array_merge($paths, ["+paths+"]);"
    out=s.replace(MARKER,MARKER+"\n"+addition,1)
    if out.count(SIGNATURE)!=1 or out.replace(MARKER+"\n"+addition,MARKER,1)!=s:
        raise RuntimeError('NOT_EXACT_PATCH')
    return out.encode('utf8')
def lint(data):
    fd,tmp=tempfile.mkstemp(suffix='.php',prefix='.mpw-b-sitemap-lint-',dir=str(SITE.parent))
    try:
        with os.fdopen(fd,'wb') as f:f.write(data)
        r=subprocess.run(['php','-l',tmp],capture_output=True,text=True,timeout=20)
        if r.returncode:raise RuntimeError('PHP_LINT_FAILED:'+r.stderr[-250:])
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def atomic(data):
    fd,tmp=tempfile.mkstemp(prefix='.mpw-b-sitemap-',dir=str(SITE.parent))
    try:
        os.fchmod(fd,SITE.stat().st_mode & 0o777)
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,SITE)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def main(action,run):
    if not re.fullmatch(r'[0-9]{6,20}',run):raise RuntimeError('INVALID_RUN_ID')
    guard()
    d=BACKUPS/run
    if action=='apply':
        old=SITE.read_bytes();new=patch(old)
        if new==old:return
        lint(new)
        if d.exists() or d.is_symlink():raise RuntimeError('BACKUP_ALREADY_EXISTS')
        d.mkdir(parents=True,mode=0o700)
        (d/'before.php').write_bytes(old)
        (d/'manifest.json').write_text(json.dumps({'before':sha(old),'after':sha(new)}))
        if SITE.read_bytes()!=old:raise RuntimeError('CONCURRENT_CHANGE')
        atomic(new)
        if sha(SITE.read_bytes())!=sha(new):raise RuntimeError('WRITE_FAILED')
        print('MPW_SIX_CANONICAL_GUIDES_ADDED_TO_SITEMAP_SOURCE')
    elif action=='rollback':
        if not d.is_dir():print('NO_CHANGE_TO_ROLLBACK');return
        m=json.loads((d/'manifest.json').read_text())
        old=(d/'before.php').read_bytes()
        if sha(old)!=m['before']:raise RuntimeError('BACKUP_INVALID')
        if sha(SITE.read_bytes())==m['before']:return
        if sha(SITE.read_bytes())!=m['after']:raise RuntimeError('CONCURRENT_CHANGE_ROLLBACK_REFUSED')
        atomic(old);print('MPW_SITEMAP_ROLLBACK_OK')
    else:raise RuntimeError('INVALID_ACTION')
if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('usage: apply|rollback numeric_run_id')
    main(sys.argv[1],sys.argv[2])
