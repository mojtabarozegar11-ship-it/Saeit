#!/usr/bin/env python3
"""Transactional root-only circular company favicon deployment; version 20261019."""
from pathlib import Path
import base64, hashlib, os, re, shutil, subprocess, sys

VERSION = '20261019'
root = Path.home() / 'public_html'
stage = Path(sys.argv[1]).resolve()
backup = stage.parent / 'original'
index = root / 'index.html'
ico = root / 'favicon.ico'
htaccess = root / '.htaccess'
asset = root / 'static/site/zomorod-brand-round-20261019'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read_icon(name):
    return base64.b64decode((stage / (name+'.b64')).read_text().strip(), validate=True)

assert stage.is_dir() and index.is_file() and ico.is_file() and htaccess.is_file()
assert not any(p.is_symlink() for p in (index, ico, htaccess))
assert not asset.exists(), "New asset directory already exists; refusing overwrite"
icons = {name: read_icon(name) for name in ('favicon.ico','icon-180.png','icon-192.png')}
assert icons['favicon.ico'].startswith(b'\x00\x00\x01\x00')
assert icons['icon-180.png'].startswith(b'\x89PNG\r\n\x1a\n')
assert icons['icon-192.png'].startswith(b'\x89PNG\r\n\x1a\n')
original_html = index.read_bytes()
original_ico = ico.read_bytes()
original_htaccess_hash = digest(htaccess.read_bytes())
assert len(original_html) > 50000 and original_html.lower().count(b'</head>') == 1
head, body = re.split(br'</head>', original_html, maxsplit=1, flags=re.I)
assert b'<main' in body and b'</main>' in body
assert b'zm-official-brand-icon-20261018' in head, "Unexpected homepage; abort to avoid damaging unrelated content"
protected = []
for sub in ('company','about','agriculture','industry','research','knowledge','services','business','tala','mohammad','ghanadi','amozeshgah'):
    for name in ('index.html','index.php'):
        p = root/sub/name
        if p.is_file() and not p.is_symlink():
            protected.append((p,digest(p.read_bytes())))
# Remove old favicon declarations only; preserve title, SEO, all other head metadata, and the entire body.
head = re.sub(br'<link\b(?=[^>]*\brel\s*=\s*["\'](?:shortcut icon|icon|apple-touch-icon)["\'])[^>]*>', b'', head, flags=re.I)
head = head.replace(b'<!-- zm-official-brand-icon-20261018 -->', b'')
tags = ('<link rel="icon" type="image/x-icon" href="/favicon.ico?v=20261019">'
        '<link rel="icon" type="image/png" sizes="192x192" href="/static/site/zomorod-brand-round-20261019/icon-192.png">'
        '<link rel="apple-touch-icon" sizes="180x180" href="/static/site/zomorod-brand-round-20261019/icon-180.png">'
        '<!-- zm-round-transparent-favicon-20261019 -->').encode()
updated_html = head + tags + b'</head>' + body
assert updated_html.split(b'</head>',1)[1] == body
assert updated_html.count(b'zm-round-transparent-favicon-20261019') == 1
backup.mkdir(mode=0o700,exist_ok=False)
shutil.copy2(index, backup / 'index.html')
shutil.copy2(ico, backup / 'favicon.ico')
assert (backup / 'index.html').read_bytes() == original_html
assert (backup / 'favicon.ico').read_bytes() == original_ico

def atomic(path, data):
    temp = path.with_name(path.name + '.zm-favicon-tmp')
    assert not temp.exists()
    temp.write_bytes(data)
    os.chmod(temp, 0o644)
    os.replace(temp, path)

def live(path, expected=None):
    result = subprocess.run(
        ['curl','--fail','--silent','--show-error','--location','--max-time','25',
         '-H','Cache-Control: no-cache','https://zomorodmelal.ir' + path],
         capture_output=True, timeout=30)
    assert result.returncode == 0, ('HTTP error',path,result.stderr[-200:])
    if expected is not None:
        assert digest(result.stdout) == digest(expected), ('Public favicon bytes mismatch',path)
    return result.stdout

made_dir = changed_ico = changed_index = False
try:
    asset.mkdir(mode=0o755)
    made_dir = True
    for name in ('icon-180.png','icon-192.png'):
        dest = asset / name
        dest.write_bytes(icons[name])
        os.chmod(dest,0o644)
    assert ico.read_bytes() == original_ico and index.read_bytes() == original_html
    atomic(ico, icons['favicon.ico'])
    changed_ico = True
    atomic(index, updated_html)
    changed_index = True
    live('/favicon.ico?v=20261019', icons['favicon.ico'])
    live('/static/site/zomorod-brand-round-20261019/icon-192.png', icons['icon-192.png'])
    html = live('/?favicon_round_20261019=1')
    assert b'zm-round-transparent-favicon-20261019' in html
    assert b'/favicon.ico?v=20261019' in html
    assert digest(htaccess.read_bytes()) == original_htaccess_hash
    assert all(digest(p.read_bytes()) == hash_ for p,hash_ in protected)
    print('ZOMOROD_ROUND_FAVICON_DEPLOY=success')
    print('ZOMOROD_ROUND_FAVICON_SHA256='+digest(icons['favicon.ico']))
    print('ZOMOROD_HOMEPAGE_BODY_UNCHANGED=yes')
    print('ZOMOROD_SUBSITES_UNCHANGED=yes')
except BaseException:
    if changed_index: atomic(index, original_html)
    if changed_ico: atomic(ico, original_ico)
    if made_dir:
        for name in ('icon-180.png','icon-192.png'):
            (asset/name).unlink(missing_ok=True)
        try: asset.rmdir()
        except OSError: pass
    print('ZOMOROD_ROUND_FAVICON_ROLLBACK=restored')
    raise
