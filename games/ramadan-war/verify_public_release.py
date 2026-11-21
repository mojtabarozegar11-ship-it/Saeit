#!/usr/bin/env python3
"""Verify every published Ramadan War asset against the exact release bytes."""
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

LIVE_URL = 'https://zomorodmelal.ir/ramadan-war/'


def verify_public_assets(base_url, source_dir, assets, opener=urlopen):
    parts = urlsplit(base_url)
    if (not base_url.endswith('/') or parts.scheme != 'https' or not parts.hostname
            or parts.username or parts.password or parts.query or parts.fragment):
        raise ValueError('game URL must be an HTTPS directory without credentials or query')
    root = Path(source_dir)
    for rel in assets:
        path = Path(rel)
        if (not rel or path.is_absolute() or '..' in path.parts
                or '\\' in rel or path.as_posix() != rel):
            raise ValueError('unsafe asset path: ' + str(rel))
        source = root / path
        # A symlinked ancestor can escape the checkout even if the leaf is a regular file.
        linked = any((root.joinpath(*path.parts[:n])).is_symlink()
                     for n in range(1, len(path.parts) + 1))
        if not source.is_file() or linked or not source.resolve().is_relative_to(root.resolve()):
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
            # A redirect to a mirror or another path does not prove that the live
            # deployment contains these exact bytes at the expected URL.
            if response.geturl() != url:
                raise RuntimeError('live asset redirected: ' + rel)
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
