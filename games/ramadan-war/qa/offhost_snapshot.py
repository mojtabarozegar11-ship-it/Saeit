#!/usr/bin/env python3
"""Read-only, bounded Ramadan War snapshot; verify rollback from an archive.

The cPanel modes never create, rename, or delete anything under public_html.
The verify mode runs on an isolated CI runner and proves file-level recovery.
"""
import hashlib
import io
import json
import os
import stat
import sys
import tarfile
import tempfile
from pathlib import Path

LIVE_ROOT = Path('/home/zomorod2/public_html')
MAX_FILES = 160
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_FILE_BYTES = 60 * 1024 * 1024
REQUIRED = frozenset({
    'index.html',
    'ramadan-war/.htaccess',
    'ramadan-war/index.html',
    'ramadan-war/game.js',
    'ramadan-war/game.css',
    'ramadan-war/engine3d.js',
    'ramadan-war/three.module.js',
    'ramadan-war/three.core.min.js',
    'ramadan-war/THREE-LICENSE.txt',
})


def require(condition, message):
    if not condition:
        raise ValueError(message)


def hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def scoped_files(root=LIVE_ROOT):
    root = Path(root)
    game = root / 'ramadan-war'
    require(root.is_dir() and not root.is_symlink(), 'unsafe public_html root')
    require(game.is_dir() and not game.is_symlink(), 'unsafe game directory')
    # Do not follow symlinks or archive content outside this exact game route.
    candidates = [root / 'index.html', *sorted(game.rglob('*'))]
    records = []
    total = 0
    for path in candidates:
        require(not path.is_symlink(), 'symlink under game route refused')
        if path.is_dir():
            continue
        require(path.is_file(), 'non-regular game path refused')
        st = path.lstat()
        require(stat.S_ISREG(st.st_mode), 'non-regular game file refused')
        name = path.relative_to(root).as_posix()
        require(name == 'index.html' or name.startswith('ramadan-war/'),
                'out-of-scope file refused')
        require(0 < st.st_size <= MAX_FILE_BYTES, 'oversized or empty file refused')
        total += st.st_size
        require(total <= MAX_TOTAL_BYTES, 'oversized game backup refused')
        require(len(records) < MAX_FILES, 'too many game files refused')
        records.append({'path': name, 'bytes': st.st_size,
                        'sha256': hash_file(path)})
    names = {row['path'] for row in records}
    require(REQUIRED.issubset(names), 'essential live game files missing')
    return {'format': 'ramadan-war-offhost-snapshot-v1',
            'files': records, 'file_count': len(records), 'total_bytes': total}


def write_archive(root, manifest, output):
    root = Path(root)
    with tarfile.open(fileobj=output, mode='w|gz', format=tarfile.PAX_FORMAT) as archive:
        for record in manifest['files']:
            path = root / record['path']
            require(path.is_file() and not path.is_symlink(), 'source path changed')
            st = path.stat()
            require(st.st_size == record['bytes'], 'source size changed')
            info = tarfile.TarInfo(record['path'])
            info.size = record['bytes']
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            info.mtime = 0
            with path.open('rb') as stream:
                archive.addfile(info, stream)
    require(scoped_files(root) == manifest, 'live files changed during backup')


def verify_archive(manifest, archive_path):
    require(manifest.get('format') == 'ramadan-war-offhost-snapshot-v1',
            'unsupported snapshot manifest')
    wanted = {r['path']: r for r in manifest['files']}
    require(len(wanted) == len(manifest['files']), 'duplicate manifest names')
    require(REQUIRED.issubset(wanted), 'incomplete backup manifest')
    require(len(wanted) <= MAX_FILES, 'oversized manifest file count')
    require(sum(r['bytes'] for r in wanted.values()) == manifest['total_bytes']
            <= MAX_TOTAL_BYTES, 'manifest byte count mismatch')
    seen = set()
    with tempfile.TemporaryDirectory(prefix='ramadan-restore-drill-') as tmp:
        restore_root = Path(tmp)
        with tarfile.open(archive_path, 'r:gz') as archive:
            for member in archive:
                name = member.name
                require(member.isfile() and not member.issym() and not member.islnk(),
                        'non-file tar member refused')
                require(name in wanted and name not in seen, 'unexpected or duplicate member')
                require(name == 'index.html' or name.startswith('ramadan-war/'),
                        'out-of-scope tar member refused')
                require('..' not in Path(name).parts and not Path(name).is_absolute(),
                        'tar path traversal refused')
                require(member.size == wanted[name]['bytes'] <= MAX_FILE_BYTES,
                        'tar member length mismatch')
                data = archive.extractfile(member).read()
                require(hashlib.sha256(data).hexdigest() == wanted[name]['sha256'],
                        'tar content checksum mismatch')
                target = restore_root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                require(hash_file(target) == wanted[name]['sha256'],
                        'isolated restore checksum mismatch')
                seen.add(name)
        require(seen == set(wanted), 'tar members missing')
    return {'verified_files': len(seen),
            'verified_bytes': manifest['total_bytes'], 'isolated_restore': 'PASS',
            'production_touched': False}


def main(args):
    require(args, 'usage: inspect [root] | pack [root] | verify manifest archive')
    action = args[0]
    if action in ('inspect', 'pack'):
        require(len(args) <= 2, 'invalid cPanel arguments')
        root = Path(args[1]) if len(args) == 2 else LIVE_ROOT
        require(root == LIVE_ROOT or os.environ.get('RAMADAN_OFFHOST_LOCAL_TEST') == '1',
                'non-production snapshot root refused')
        manifest = scoped_files(root)
        if action == 'inspect':
            print(json.dumps(manifest, sort_keys=True))
        else:
            write_archive(root, manifest, sys.stdout.buffer)
    elif action == 'verify':
        require(len(args) == 3, 'verify requires manifest and archive')
        manifest = json.loads(Path(args[1]).read_text('utf-8'))
        print(json.dumps(verify_archive(manifest, args[2]), sort_keys=True))
    else:
        raise ValueError('unsupported snapshot action')


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except (ValueError, OSError, tarfile.TarError, json.JSONDecodeError) as exc:
        print('RAMADAN_OFFHOST_SNAPSHOT_FAIL: ' + str(exc), file=sys.stderr)
        raise SystemExit(2)
