#!/usr/bin/env python3
"""G-01 -> S-01: READ-ONLY Ramadan Web release preflight. No SSH/deploy/write."""
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

def deployment_assets(source):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ASSETS' for t in node.targets):
            value = ast.literal_eval(node.value)
            if not isinstance(value, list) or not value or not all(isinstance(x, str) for x in value):
                raise ValueError('ASSETS must be a nonempty static list')
            return value
    raise ValueError('deploy.py has no static ASSETS declaration')

def audit(root, deploy_source, manifest_source):
    root = Path(root)
    assets = deployment_assets(deploy_source)
    manifest = json.loads(manifest_source)
    checksums = manifest.get('sha256')
    if not isinstance(checksums, dict) or manifest.get('version') != 'R40':
        raise ValueError('R40 manifest absent or invalid')
    if len(assets) != len(set(assets)):
        raise ValueError('Duplicate deployment assets')
    errors = []
    for name in assets:
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or not p.parts or '\\' in name:
            errors.append('unsafe-path:'+name);continue
        file = root.joinpath(*p.parts)
        if file.is_symlink() or not file.is_file():
            errors.append('missing-or-symlink:'+name);continue
        expected = checksums.get(name)
        if not isinstance(expected, str) or len(expected) != 64:
            errors.append('unmanifested:'+name);continue
        actual = hashlib.sha256(file.read_bytes()).hexdigest()
        if actual != expected:errors.append('sha-mismatch:'+name)
    # Any imported local JS runtime must be transferred by the guarded deploy contract.
    js = (root/'game.js').read_text(encoding='utf-8')
    for name in re.findall(r"from\s*['\"]\./([^'\"]+)['\"]", js):
        if name not in assets:errors.append('missing-js-import-in-deploy:'+name)
    return {'status':'PASS' if not errors else 'FAIL','asset_count':len(assets),'errors':errors}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game_root',type=Path)
    parser.add_argument('deploy_py',type=Path)
    parser.add_argument('manifest_json',type=Path)
    args=parser.parse_args()
    result=audit(args.game_root,args.deploy_py.read_text(),args.manifest_json.read_text())
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['status']=='PASS' else 2)

if __name__=='__main__':main()
