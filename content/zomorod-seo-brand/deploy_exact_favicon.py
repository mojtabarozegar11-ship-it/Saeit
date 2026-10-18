#!/usr/bin/env python3
"""Install only official root favicon and three main-domain icon head tags; reversible."""
from pathlib import Path
import base64,hashlib,os,re,shutil,subprocess,sys
root=Path.home()/'public_html'
stage=Path(sys.argv[1]).resolve()
backup=stage.parent/'original'
ico=root/'favicon.ico'
index=root/'index.html'
asset=root/'static/site/zomorod-brand-20261018'
assert stage.is_dir() and not asset.exists() and index.is_file() and not index.is_symlink()
assert ico.is_file() and not ico.is_symlink()
assert (root/'.htaccess').is_file() and not (root/'.htaccess').is_symlink()
backup.mkdir(mode=0o700,exist_ok=False)
def shaf(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def decode(n):return base64.b64decode((stage/(n+'.b64')).read_text().strip(),validate=True)
icons={'favicon.ico':decode('favicon.ico'),'icon-180.png':decode('icon-180.png'),'icon-192.png':decode('icon-192.png')}
assert icons['favicon.ico'][:4]==b'\x00\x00\x01\x00'
assert icons['icon-180.png'][:8]==icons['icon-192.png'][:8]==b'\x89PNG\r\n\x1a\n'
old=index.read_bytes()
assert old.lower().count(b'</head>')==1 and len(old)>50000
assert b'zm-official-brand-icon-20261018' not in old
head=old.split(b'</head>',1)[0]
body=old.split(b'</head>',1)[1]
assert b'<main' in body and b'</main>' in body
prior={'index.html':shaf(index),'favicon.ico':shaf(ico),'.htaccess':shaf(root/'.htaccess')}
protected=[]
for sub in ('company','about','agriculture','industry','research','knowledge','services','business','tala','mohammad','ghanadi','amozeshgah'):
    for n in ('index.html','index.php'):
        f=root/sub/n
        if f.is_file() and not f.is_symlink():
            protected.append((f,shaf(f)))
shutil.copy2(index,backup/'index.html')
shutil.copy2(ico,backup/'favicon.ico')
assert (backup/'index.html').read_bytes()==old
assert (backup/'favicon.ico').read_bytes()==ico.read_bytes()
# New declarations in the root head, leave all editorial content and old tags untouched.
tags=('<meta name="application-name" content="شرکت کشت و صنعت زمرد ملل | Zomorod Mell">'
      '<link rel="icon" type="image/x-icon" sizes="any" href="/favicon.ico?v=20261018">'
      '<link rel="icon" type="image/png" sizes="192x192" href="/static/site/zomorod-brand-20261018/icon-192.png">'
      '<link rel="apple-touch-icon" sizes="180x180" href="/static/site/zomorod-brand-20261018/icon-180.png">'
      '<!-- zm-official-brand-icon-20261018 -->').encode()
# Avoid preexisting icon declarations superseding the new one in browser choices.
# Keep content unchanged outside <head>.
head=re.sub(br'<link\b(?=[^>]*\brel=["\'](?:shortcut icon|icon|apple-touch-icon)["\'])[^>]*>',b'',head,flags=re.I)
new=head+tags+b'</head>'+body
assert new.split(b'</head>',1)[1]==body
assert new.count(b'zm-official-brand-icon-20261018')==1
def atomic(target,data,mode):
    temp=target.with_name(target.name+'.zomorod-official-next')
    assert not temp.exists()
    temp.write_bytes(data)
    os.chmod(temp,mode)
    os.replace(temp,target)
def status(path,expected=None):
    url='https://zomorodmelal.ir'+path
    r=subprocess.run(['curl','--silent','--show-error','--location','--max-time','22','-H','Cache-Control: no-cache','-o','-',url],capture_output=True,timeout=27)
    assert r.returncode==0,('HTTP failure',path)
    if expected is not None:assert hashlib.sha256(r.stdout).digest()==hashlib.sha256(expected).digest(),('Public bytes differ',path)
    return r.stdout
created=False;icon_changed=False;root_changed=False
try:
    asset.mkdir(mode=0o755)
    created=True
    for name in ('icon-180.png','icon-192.png'):
        (asset/name).write_bytes(icons[name])
        os.chmod(asset/name,0o644)
    assert ico.is_file() and shaf(ico)==prior['favicon.ico']
    atomic(ico,icons['favicon.ico'],0o644);icon_changed=True
    assert shaf(index)==prior['index.html']
    atomic(index,new,0o644);root_changed=True
    status('/favicon.ico?v=20261018',icons['favicon.ico'])
    status('/static/site/zomorod-brand-20261018/icon-192.png',icons['icon-192.png'])
    html=status('/?official_favicon=20261018')
    assert b'zm-official-brand-icon-20261018' in html
    assert b'/favicon.ico?v=20261018' in html
    assert shaf(root/'.htaccess')==prior['.htaccess']
    assert all(shaf(p)==h for p,h in protected)
    print('ZOMOROD_FAVICON_DEPLOY=success')
    print('ZOMOROD_FAVICON_SHA256='+hashlib.sha256(icons['favicon.ico']).hexdigest())
    print('ZOMOROD_HOMEPAGE_CONTENT_PRESERVED=yes')
    print('ZOMOROD_SUBSITES_IMMUTABLE=verified')
except BaseException:
    if root_changed:atomic(index,(backup/'index.html').read_bytes(),0o644)
    if icon_changed:atomic(ico,(backup/'favicon.ico').read_bytes(),0o644)
    if created:
        for name in ('icon-180.png','icon-192.png'):
            (asset/name).unlink(missing_ok=True)
        try:asset.rmdir()
        except OSError:pass
    print('ZOMOROD_FAVICON_ROLLBACK=restored')
    raise
