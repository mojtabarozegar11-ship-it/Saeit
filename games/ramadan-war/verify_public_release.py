#!/usr/bin/env python3
"""Verify every published Ramadan War asset against the exact release bytes."""
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

LIVE_URL = 'https://zomorodmelal.ir/ramadan-war/'


def verify_public_assets(base_url, source_dir, assets, opener=urlopen):
    if not base_url.endswith('/'):
        raise ValueError('game URL must end with /')
    for rel in assets:
        path = Path(rel)
        if not rel or path.is_absolute() or '..' in path.parts:
            raise ValueError('unsafe asset path: ' + str(rel))
        source = Path(source_dir) / path
        if not source.is_file() or source.is_symlink():
            raise RuntimeError('release asset missing or linked: ' + rel)
        expected = source.read_bytes()
        expected_hash = sha256(expected).hexdigest()
        url = base_url + quote(rel, safe='/') + '?release_sha256=' + expected_hash[:16]
        request = Request(url, headers={
            'Cache-Control': 'no-cache, no-store',
            'Pragma': 'no-cache',
            'User-Agent': 'RamadanReleaseHashGuard/1',
        })
        with opener(request, timeout=35) as response:
            if response.status != 200:
                raise RuntimeError('live asset HTTP status mismatch: ' + rel)
            actual = response.read(len(expected) + 1)
        if len(actual) != len(expected) or sha256(actual).hexdigest() != expected_hash:
            raise RuntimeError('live asset SHA-256 mismatch: ' + rel)
    return len(assets)


if __name__ == '__main__':
    from deploy import ASSETS
    count = verify_public_assets(LIVE_URL, Path(__file__).resolve().parent, ASSETS)
    print('RAMADAN_LIVE_ALL_ASSET_SHA256_PASS=' + str(count), flush=True)
