#!/usr/bin/env python3
"""Verify Zomorod ERP development bundles without extracting or running code."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


def check_entries(items: dict[str, bytes], basename: str) -> int:
    prefix=basename+'/'
    if any(not n.startswith(prefix) or '..' in PurePosixPath(n).parts or
           PurePosixPath(n).is_absolute() or not n.endswith(('.json','.php','.py','.md','.yml','.htaccess'))
           for n in items):
        raise ValueError('Unsafe or unexpected bundle file path')
    root=prefix+'MANIFEST.json'
    if root not in items:
        raise ValueError('Missing manifest')
    meta=json.loads(items[root])
    if meta.get('status')!='DEVELOPMENT_ONLY_NOT_PRODUCTION_DEPLOYABLE' or (
        meta.get('secret_material_included') is not False or
        meta.get('production_data_included') is not False or
        meta.get('live_website_modified') is not False):
        raise ValueError('Unsafe bundle metadata')
    listed=meta.get('files')
    if not isinstance(listed,list) or len(listed)<20:
        raise ValueError('Missing source hashes')
    expected={root}
    for obj in listed:
        path=obj['path']
        name=prefix+path
        if name in expected or name not in items:
            raise ValueError('Missing or repeated manifest path')
        expected.add(name)
        raw=items[name]
        if len(raw)!=obj['bytes'] or hashlib.sha256(raw).hexdigest()!=obj['sha256']:
            raise ValueError('Source mismatch: '+path)
    if set(items)!=expected:
        raise ValueError('Unexpected file in bundle')
    return len(items)


def verify(path: Path) -> int:
    basename=path.name.removesuffix('.tar.gz').removesuffix('.zip')
    if path.name.endswith('.zip'):
        with zipfile.ZipFile(path) as z:
            names=z.namelist()
            if len(names)!=len(set(names)):
                raise ValueError('Duplicate archive entries')
            if any(z.getinfo(name).is_dir() for name in names):
                raise ValueError('Directory entries not expected')
            data={n:z.read(n) for n in names}
    elif path.name.endswith('.tar.gz'):
        with tarfile.open(path,'r:gz') as t:
            members=t.getmembers()
            if len({m.name for m in members})!=len(members) or any(not m.isfile() for m in members):
                raise ValueError('Nonregular or duplicate archive entry')
            data={m.name:t.extractfile(m).read() for m in members}
    else:
        raise ValueError('Unsupported package format')
    return check_entries(data,basename)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packages',nargs='+',type=Path)
    args=parser.parse_args()
    for package in args.packages:
        count=verify(package)
        print(f'PACKAGE_SHA256_MANIFEST=PASS file_count={count} path={package}')
