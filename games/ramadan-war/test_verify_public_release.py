#!/usr/bin/env python3
"""Offline failure-mode tests for the public release byte-for-byte gate."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('verify_public_release', Path(__file__).with_name('verify_public_release.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
verify_public_assets = module.verify_public_assets


class Response:
    def __init__(self, body, status=200):
        self.body, self.status = body, status
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, size):
        return self.body[:size]


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'three-addons').mkdir()
        (self.root / 'game.js').write_bytes(b'new release JS')
        (self.root / 'three-addons/loader.js').write_bytes(b'new loader')
        self.assets = ['game.js', 'three-addons/loader.js']
        self.responses = {name: (self.root / name).read_bytes() for name in self.assets}
        self.requests = []

    def opener(self, request, timeout):
        self.assertEqual(timeout, 35)
        self.assertIn('no-cache', request.get_header('Cache-control'))
        self.assertIn('release_sha256=', request.full_url)
        self.requests.append(request.full_url)
        name = request.full_url.split('/ramadan-war/', 1)[1].split('?', 1)[0]
        return Response(self.responses[name])

    def check(self):
        return verify_public_assets('https://example.test/ramadan-war/', self.root,
                                    self.assets, self.opener)

    def test_exact_release_bytes_pass_including_nested_assets(self):
        self.assertEqual(self.check(), 2)
        self.assertEqual(len(self.requests), 2)

    def test_stale_asset_fails_closed(self):
        self.responses['game.js'] = b'old release JS'
        with self.assertRaisesRegex(RuntimeError, 'SHA-256 mismatch: game.js'):
            self.check()

    def test_extra_bytes_fail_closed(self):
        self.responses['game.js'] += b'\nUNEXPECTED'
        with self.assertRaisesRegex(RuntimeError, 'SHA-256 mismatch: game.js'):
            self.check()

    def test_missing_local_asset_and_unsafe_path_fail_closed(self):
        (self.root / 'game.js').unlink()
        with self.assertRaisesRegex(RuntimeError, 'missing or linked'):
            self.check()
        with self.assertRaisesRegex(ValueError, 'unsafe asset path'):
            verify_public_assets('https://example.test/ramadan-war/', self.root,
                                 ['../private'], self.opener)


if __name__ == '__main__':
    unittest.main()
