#!/usr/bin/env python3
"""Verify separately encrypted cPanel extra-root archive without extraction.

Decrypted bytes arrive via pinned SSH and a second validated GPG+SHA256 proof.
Only aggregate counts are returned. No paths/targets/customer data are printed.
This is not a complete functional restore or a permission to take payments.
"""
from __future__ import annotations
import json
import sys
import tarfile
from pathlib import PurePosixPath

MAX_FILES=150000
MAX_BYTES=512*1024*1024
EXCLUDED_ROOTS={'Saeit-staging','mojplaywin.com'}
def inspect(stream):
    roots=set()
    seen=set()
    counts={'regular':0,'directories':0,'links':0,'special':0,
            'regular_bytes':0,'unsafe_members':0,'members':0}
    with tarfile.open(fileobj=stream,mode='r|') as t:
        for item in t:
            if counts['members']>=MAX_FILES:
                raise ValueError('member limit')
            counts['members']+=1
            name=item.name
            if not name or name.startswith('/') or name.startswith('./'):
                counts['unsafe_members']+=1
                raise ValueError('unsafe tar member')
            parts=PurePosixPath(name).parts
            if len(parts)<1 or '..' in parts or parts[0] in EXCLUDED_ROOTS:
                counts['unsafe_members']+=1
                raise ValueError('out-of-scope tar member')
            canonical='/'.join(parts)
            if canonical in seen:
                raise ValueError('duplicate tar name')
            seen.add(canonical)
            roots.add(parts[0])
            if item.isfile():
                if item.size<0:
                    raise ValueError('size invalid')
                counts['regular']+=1
                counts['regular_bytes']+=item.size
                if counts['regular_bytes']>MAX_BYTES:
                    raise ValueError('archive too large')
            elif item.isdir():
                counts['directories']+=1
            elif item.issym() or item.islnk():
                counts['links']+=1
            else:
                counts['special']+=1
                raise ValueError('special file forbidden')
    while stream.read(131072):
        pass
    if not 1<=len(roots)<=3 or counts['regular']<1:
        raise ValueError('archive roots or ordinary files absent')
    return {
        'classification':'MOJ_COMMERCE_V12_EXTRA_WEBROOTS_ARCHIVE_VERIFIED_METADATA',
        'archive_roots_aggregate_count':len(roots),
        'totals':counts,'source_archive_stream_read':True,
        'safe_isolated_extraction_performed':False,
        'full_site_restore_verified':False,
        'independent_recovery_key_escrow_verified':False,
        'production_modified':False,'release_permitted':False
    }

if __name__=='__main__':
    try:
        if sys.argv[1:]!=['archive']:
            raise RuntimeError('unsupported verifier mode')
        print(json.dumps(inspect(sys.stdin.buffer),sort_keys=True))
    except Exception:
        print(json.dumps({'classification':'MOJ_COMMERCE_V12_EXTRA_WEBROOTS_UNVERIFIED',
                          'release_permitted':False,'error':'SANITIZED_FAILURE'}))
        raise SystemExit(1)
