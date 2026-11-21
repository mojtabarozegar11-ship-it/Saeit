#!/usr/bin/env python3
"""Narrow, no-write checkout asset inventory; never prints source content."""
from __future__ import annotations
import json
import os
from pathlib import Path
import pwd

BASE = Path('/home/zomorod2')
ROOTS = {'web': BASE/'mojplaywin.com', 'staging': BASE/'Saeit-staging'}
NAMES = {'home-shared-v1.css', 'mpw-fintech-checkout-v2.css'}
EXCLUDE = {'.git','node_modules','venv','virtualenv','.venv','__pycache__','site-packages'}


def diagnostic():
    if pwd.getpwuid(os.getuid()).pw_name != 'zomorod2':
        raise SystemExit('Wrong cPanel identity')
    out = {'scope':'mpw-checkout-assets-readonly','writes':0,'roots':{},
           'asset_candidates':[],'source_references':[]}
    for label, folder in {
        'private_backup': BASE/'.private_mojplaywin_main_agents',
        'public_revenue':ROOTS['web']/'mpw-editorial'/'revenue',
        'public_asset_dir':ROOTS['web']/'mpw-editorial'/'revenue'/'assets',
        'original_home_folder':ROOTS['web']/'design-preview-20261017',
    }.items():
        out.setdefault('directory_health',{})[label]={
            'exists':folder.exists(),'is_dir':folder.is_dir(),
            'symlink':folder.is_symlink(),
            'private_permissions_ok':(not bool(folder.stat().st_mode & 0o077)) if label=='private_backup' and folder.exists() else None,
        }
    for label, path in {
        'original_home_html':ROOTS['web']/'design-preview-20261017'/'production-home-20261017.html',
        'passenger_entry':ROOTS['web']/'passenger_wsgi.py',
        'routing':ROOTS['web']/'.htaccess',
    }.items():
        out.setdefault('file_health',{})[label]={
            'is_file':path.is_file(),'symlink':path.is_symlink()}
    for label, root in ROOTS.items():
        out['roots'][label]={'exists':root.is_dir(),'symlink':root.is_symlink()}
        if not root.is_dir() or root.is_symlink():
            continue
        for parent, dirs, files in os.walk(root,followlinks=False):
            folder=Path(parent)
            depth=len(folder.relative_to(root).parts)
            dirs[:]=([d for d in dirs if d not in EXCLUDE and not (folder/d).is_symlink()]
                     if depth < 7 else [])
            for filename in files:
                file=folder/filename
                if file.is_symlink():
                    continue
                rel=str(file.relative_to(root))
                if filename in NAMES and len(out['asset_candidates'])<40:
                    out['asset_candidates'].append({'root':label,'file':rel,'bytes':file.stat().st_size})
                if (len(out['source_references'])<25
                    and filename.endswith(('.py','.html','.php','.js'))
                    and file.stat().st_size<150000):
                    try: src=file.read_text('utf8','replace')
                    except OSError: continue
                    hits=sorted(name for name in NAMES if name in src)
                    if hits:
                        out['source_references'].append({'root':label,'file':rel,'asset_names':hits})
    for name in sorted(NAMES):
        path=ROOTS['web']/'mpw-editorial'/'revenue'/'assets'/name
        out.setdefault('missing_live_assets',{})[name]=not path.is_file()
    return out

if __name__=='__main__':
    print('MPW_CHECKOUT_ASSET_INVENTORY='+json.dumps(diagnostic(),sort_keys=True))
