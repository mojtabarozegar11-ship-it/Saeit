"""Security and isolated restore regression tests for the off-host game snapshot."""
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

import offhost_snapshot as snapshot


class OffhostSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ramadan-snapshot-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'public_html'
        for path in sorted(snapshot.REQUIRED | {'ramadan-war/images/extra.webp'}):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(('source:' + path).encode('utf-8'))

    def archive(self):
        manifest = snapshot.scoped_files(self.root)
        binary = io.BytesIO()
        snapshot.write_archive(self.root, manifest, binary)
        target = Path(self.temp.name) / 'live-backup.tar.gz'
        target.write_bytes(binary.getvalue())
        return manifest, target

    def test_scoped_inventory_and_isolated_full_restore(self):
        manifest, target = self.archive()
        self.assertEqual(manifest['file_count'], len(snapshot.REQUIRED) + 1)
        self.assertEqual(
            manifest['total_bytes'],
            sum(row['bytes'] for row in manifest['files']),
        )
        self.assertEqual(
            snapshot.verify_archive(manifest, target),
            {'verified_files': len(snapshot.REQUIRED) + 1,
             'verified_bytes': manifest['total_bytes'],
             'isolated_restore': 'PASS', 'production_touched': False},
        )

    def test_missing_critical_live_component_is_rejected(self):
        (self.root / 'ramadan-war/game.js').unlink()
        with self.assertRaisesRegex(ValueError, 'essential live game files missing'):
            snapshot.scoped_files(self.root)

    def test_symlink_in_game_route_is_rejected(self):
        (self.root / 'ramadan-war/leak').symlink_to(self.root / 'index.html')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            snapshot.scoped_files(self.root)

    def test_live_change_after_inventory_is_rejected(self):
        manifest = snapshot.scoped_files(self.root)
        (self.root / 'ramadan-war/game.js').write_bytes(b'source changed')
        with self.assertRaisesRegex(ValueError, 'source size changed|live files changed'):
            snapshot.write_archive(self.root, manifest, io.BytesIO())

    def test_modified_archive_is_rejected(self):
        manifest, target = self.archive()
        corrupted = Path(self.temp.name) / 'modified.tar.gz'
        with tarfile.open(corrupted, 'w:gz') as out:
            with tarfile.open(target, 'r:gz') as source:
                for member in source:
                    content = source.extractfile(member).read()
                    if member.name == 'ramadan-war/game.js':
                        content = content[:1] + b'Q' + content[2:]
                    member.size = len(content)
                    out.addfile(member, io.BytesIO(content))
        with self.assertRaisesRegex(ValueError, 'checksum'):
            snapshot.verify_archive(manifest, corrupted)

    def test_extra_member_and_path_traversal_rejected(self):
        manifest, target = self.archive()
        corrupt = Path(self.temp.name) / 'inject.tar.gz'
        with tarfile.open(corrupt, 'w:gz') as out:
            with tarfile.open(target, 'r:gz') as source:
                for member in source:
                    out.addfile(member, source.extractfile(member))
            data = b'denied'
            extra = tarfile.TarInfo('../outside.txt')
            extra.size = len(data)
            out.addfile(extra, io.BytesIO(data))
        with self.assertRaisesRegex(ValueError, 'unexpected|out-of-scope|traversal'):
            snapshot.verify_archive(manifest, corrupt)
        self.assertFalse((Path(self.temp.name) / 'outside.txt').exists())

    def test_manifest_tamper_rejected(self):
        manifest, target = self.archive()
        manifest = json.loads(json.dumps(manifest))
        manifest['files'][0]['sha256'] = hashlib.sha256(b'untrusted').hexdigest()
        with self.assertRaisesRegex(ValueError, 'checksum'):
            snapshot.verify_archive(manifest, target)


if __name__ == '__main__':
    unittest.main()
