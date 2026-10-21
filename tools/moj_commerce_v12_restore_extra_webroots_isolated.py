#!/usr/bin/env python3
"""Isolated extraction of separately encrypted cPanel webroot archives.

Writes ONLY into a caller-created 0700 fresh temporary directory on a
disposable GitHub runner. No symlinks, hardlinks, special files or traversal.
No filenames, contents or proprietary metadata appear in logs.
"""
from __future__ import annotations
import json
import os
import stat
import sys
import tarfile
from pathlib import Path,PurePosixPath

MAX_ENTRIES=150000
MAX_BYTES=512*1024*1024
MIN_FREE_BYTES=512*1024*1024
EXCLUDED={'Saeit-staging','mojplaywin.com'}

def _safe_parts(name):
    if not isinstance(name,str) or not name or name.startswith('/') or name.startswith('./'):
        raise ValueError('unsafe name')
    p=PurePosixPath(name)
    parts=p.parts
    if not parts or '..' in parts or parts[0] in EXCLUDED or parts[0].startswith('.'):
        raise ValueError('unsafe root')
    return parts

def restore(stream,root):
    dest=Path(root)
    if dest.is_symlink() or not dest.is_dir() or stat.S_IMODE(dest.stat().st_mode)!=0o700:
        raise ValueError('non-private destination')
    roots=set()
    seen=set()
    report={'classification':'MOJ_COMMERCE_V12_EXTRA_ROOTS_ISOLATED_RESTORE',
            'regular_files_restored':0,'directories_restored':0,'regular_bytes_restored':0,
            'links_restored':0,'root_count_restored':0,
            'extra_root_restore_complete':False,
            'entire_cpanel_tenant_restore_proven':False,
            'independent_backup_key_escrow_verified':False,
            'production_modified':False,'release_permitted':False}
    with tarfile.open(fileobj=stream,mode='r|') as tar:
        for member in tar:
            if len(seen)>=MAX_ENTRIES:
                raise ValueError('too many entries')
            parts=_safe_parts(member.name)
            path_key='/'.join(parts)
            if path_key in seen:
                raise ValueError('duplicate member')
            seen.add(path_key)
            roots.add(parts[0])
            p=dest
            for c in parts[:-1]:
                p=p/c
                if p.is_symlink() or (p.exists() and not p.is_dir()):
                    raise ValueError('unsafe parent')
                p.mkdir(mode=0o700,exist_ok=True)
            output=p/parts[-1]
            if output.is_symlink():
                raise ValueError('symlink collision')
            if member.isdir():
                if output.exists() and not output.is_dir():
                    raise ValueError('directory collision')
                output.mkdir(mode=0o700,exist_ok=True)
                report['directories_restored']+=1
            elif member.isfile():
                if member.size<0 or report['regular_bytes_restored']+member.size>MAX_BYTES:
                    raise ValueError('payload size limit')
                disk=os.statvfs(dest)
                if disk.f_bavail*disk.f_frsize<MIN_FREE_BYTES:
                    raise ValueError('no isolated runner space')
                source=tar.extractfile(member)
                if source is None:
                    raise ValueError('missing file bytes')
                flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
                if hasattr(os,'O_NOFOLLOW'):
                    flags|=os.O_NOFOLLOW
                fd=os.open(output,flags,0o600)
                n=0
                with os.fdopen(fd,'wb') as out:
                    while True:
                        chunk=source.read(131072)
                        if not chunk:
                            break
                        n+=len(chunk)
                        out.write(chunk)
                if n!=member.size:
                    raise ValueError('truncated archive member')
                report['regular_files_restored']+=1
                report['regular_bytes_restored']+=n
            else:
                # No symlinks in the observed independently encrypted extra
                # root archive. Strictly reject them instead of following.
                raise ValueError('link or special file not accepted')
    while stream.read(131072):
        pass
    if len(roots)!=3 or report['regular_files_restored']<1:
        raise ValueError('missing one or more additional webroot trees')
    report['root_count_restored']=len(roots)
    report['extra_root_restore_complete']=True
    return report

if __name__=='__main__':
    try:
        if len(sys.argv)!=2:
            raise ValueError('isolated directory required')
        print(json.dumps(restore(sys.stdin.buffer,sys.argv[1]),sort_keys=True))
    except Exception:
        print('MOJ_COMMERCE_V12_EXTRA_ROOT_RESTORE_FAILED_NO_RELEASE',file=sys.stderr)
        raise SystemExit(1)
