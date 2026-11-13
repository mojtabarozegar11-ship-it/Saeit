#!/usr/bin/env python3
"""Pinned, reversible, 15-file Zomorod photo carousel release gate.

Read-only by default. Never creates a release merely because the source branch merges.
A production change additionally requires an explicit --owner-approved operator flag.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pwd
import re
import shutil
import stat
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path('/home/zomorod2/public_html')
BACKUP_ROOT = Path('/home/zomorod2/.backups/zomorod-fields-20261113')
FILES = ('index.html', 'assets/zm-reference-v3.css', 'assets/zm-reference-v3.js')
SLUGS = ('innovation', 'laboratory', 'greenhouse', 'livestock', 'smart-tools', 'games-simulation')
CREATED = tuple(f'assets/zm-field-{slug}.webp' for slug in SLUGS) + tuple(
    f'fields/{slug}/index.html' for slug in SLUGS
)
# The first four cards already depend on these untouched production images.
# Check them read-only before any new page may link to the carousel.
LEGACY_IMAGES = {
    'assets/zm-v3-farming.webp': (150, 90),
    'assets/zm-v3-genetics.webp': (150, 90),
    'assets/zm-v3-industry.webp': (150, 90),
    'assets/zm-v3-economy.webp': (150, 90),
}
# Exact Git blobs of the successfully verified #2251 live-release source.
OLD_BLOBS = dict(zip(FILES, (
    'afd94198a01194ee7b31be941bb305f775cacacf',
    '61c94300dd81bbddbe3b87962aec971dba05f047',
    '29d4ba1e2e3d550271d6d61614db726b024eeea3',
)))
# Exact Git blobs from PR #2254 after its 4th carousel browser tests passed.
NEW_BLOBS = dict(zip(FILES, (
    'dae8ec6e93ab6890977285a42ebb077d91314dbc',
    '63559875709de300ffabbd148bfa76c22e88abfc',
    'b5f99cf18ad8b74a2854a837bcd252bf98a1a30e',
)))
NEW_BLOBS.update({
    'fields/innovation/index.html': '52de8fba32d62415370c025d07e24a86858802c3',
    'assets/zm-field-innovation.webp': '7eab3af59d0b0b0ca62dc523d5764b65e758dadf',
    'fields/laboratory/index.html': '7b0f17d9e4aa274d8aa26e498ac3c9180385478e',
    'assets/zm-field-laboratory.webp': 'b4badc5a131fef8969438f572fdf7586c4abb885',
    'fields/greenhouse/index.html': '4c84519d45cfca323a2a32f75be8adb9837f501f',
    'assets/zm-field-greenhouse.webp': 'cc80a74e2b257f81cd6ae7af3c1c293e4bd114fb',
    'fields/livestock/index.html': '75e7efd60182fa161c8b773293ca677740a96b37',
    'assets/zm-field-livestock.webp': 'efe17aefb32524ba65ca97d07970c8dd31e209cb',
    'fields/smart-tools/index.html': '1462f5c6329f306fb9119bc6b3847ee703ca3aa1',
    'assets/zm-field-smart-tools.webp': '5b76694a87654a79c6ffa5e36546726fcdb2020e',
    'fields/games-simulation/index.html': '71114c9598348324cda26330649eddf9974ccccb',
    'assets/zm-field-games-simulation.webp': '5ed594881064288ace29973ee3100a89b9af9e3e',
})
PROTECTED = (
    '.htaccess', 'sitemap.xml', 'agriculture/index.html',
    'research/index.html', 'industry/index.html', 'services/index.html',
    'company/index.html', 'contact/index.html', 'games/index.html',
    'apps/index.html', 'auctions/index.html',
    'site-heritage/home-before-nexus-20261112/index.html',
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f'Missing or symlinked file: {path}')
    return path.read_bytes()


def identity() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('Refuse non-cPanel user')
    if ROOT.is_symlink() or not ROOT.is_dir() or ROOT != Path('/home/zomorod2/public_html'):
        raise RuntimeError('Untrusted public_html root')
    if (ROOT / 'assets').is_symlink() or not (ROOT / 'assets').is_dir():
        raise RuntimeError('Untrusted assets directory')


def safe_stage(stage: Path) -> Path:
    if not stage.is_absolute() or stage.is_symlink() or not stage.is_dir():
        raise RuntimeError('Stage must be a real absolute private directory')
    resolved = stage.resolve(strict=True)
    if resolved == ROOT.resolve() or ROOT.resolve() in resolved.parents:
        raise RuntimeError('Stage cannot be inside public_html')
    for name in ('old', 'new'):
        folder = stage / name
        if folder.is_symlink() or not folder.is_dir():
            raise RuntimeError('Missing private stage subfolder: ' + name)
        actual = {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() or p.is_symlink()}
        allowed = set(FILES if name == 'old' else FILES + CREATED)
        if actual != allowed:
            raise RuntimeError(f'Unexpected staged files in {name}: {actual ^ allowed}')
    return stage


def webp_dimensions(data: bytes) -> tuple[int, int]:
    """Inspect RIFF WebP dimensions without installing packages on the cPanel host.

    Immutable Git blob SHA pins complete bytes. CI browser tests also decode them.
    """
    if (len(data) < 30 or data[:4] != b'RIFF' or data[8:12] != b'WEBP' or
            int.from_bytes(data[4:8], 'little') + 8 != len(data)):
        raise RuntimeError('Invalid WebP RIFF file')
    kind = data[12:16]
    # The RIFF envelope alone cannot prove the first image chunk is complete.
    # Refuse truncated/oversized chunks, including forged valid-looking dimensions.
    chunk_size = int.from_bytes(data[16:20], 'little')
    chunk_end = 20 + chunk_size + (chunk_size & 1)  # RIFF chunks are word-aligned
    if (chunk_end > len(data) or
            (kind == b'VP8X' and chunk_size != 10) or
            (kind == b'VP8 ' and chunk_size < 10) or
            (kind == b'VP8L' and chunk_size < 5)):
        raise RuntimeError('Invalid WebP RIFF chunk')
    if kind == b'VP8 ' and data[23:26] == b'\x9d\x01\x2a':
        width = int.from_bytes(data[26:28], 'little') & 0x3fff
        height = int.from_bytes(data[28:30], 'little') & 0x3fff
    elif kind == b'VP8L' and len(data) >= 25:
        if data[20] != 0x2f:
            raise RuntimeError('Invalid WebP lossless header')
        width = 1 + (data[21] | ((data[22] & 0x3f) << 8))
        height = 1 + ((data[22] >> 6) | (data[23] << 2) | ((data[24] & 0x0f) << 10))
    elif kind == b'VP8X':
        width = 1 + int.from_bytes(data[24:27], 'little')
        height = 1 + int.from_bytes(data[27:30], 'little')
    else:
        raise RuntimeError('Unsupported WebP encoding')
    return (width, height)


def validate_legacy_images() -> dict[str, str]:
    """Read-only check: existing four photo cards must not become broken on release."""
    fingerprints = {}
    for name, minimum in LEGACY_IMAGES.items():
        data = read_regular(ROOT / name)
        width, height = webp_dimensions(data)
        if width < minimum[0] or height < minimum[1]:
            raise RuntimeError('Legacy card image is too small: ' + name)
        fingerprints[name] = sha256(data)
    return fingerprints


def candidates(stage: Path):
    safe_stage(stage)
    old = {name: read_regular(stage / 'old' / name) for name in FILES}
    new = {name: read_regular(stage / 'new' / name) for name in FILES + CREATED}
    for name in FILES:
        if git_blob(old[name]) != OLD_BLOBS[name]:
            raise RuntimeError('Old source does not match approved revision: ' + name)
        if old[name] == new[name]:
            raise RuntimeError('No actual change: ' + name)
    for name in FILES + CREATED:
        if git_blob(new[name]) != NEW_BLOBS[name]:
            raise RuntimeError('Candidate not approved and browser-tested: ' + name)
    page = new['index.html']
    js = new['assets/zm-reference-v3.js']
    if not (page.count(b'data-auto-strip=') == 3 and
            page.count(b'data-field-carousel=') == 1 and
            page.count(b'data-rotator-toggle=') == 4 and
            b'zm-reference-v3.js?v=20261113-fields1' in page and
            b'zm-reference-v3.css?v=20261113-fields1' in page and
            b'const strips=Array.from(document.querySelectorAll(' in js and
            b'prefers-reduced-motion' in js):
        raise RuntimeError('Candidate lacks verified four-carousel behavior')
    starts = page.split(b'<div id="fields-carousel"', 1)
    if len(starts) != 2:
        raise RuntimeError('Missing original photo carousel')
    body = starts[1].split(b'</div><button class="auto-rotator-toggle fields-rotator-toggle"', 1)
    if len(body) != 2:
        raise RuntimeError('Photo carousel markup boundary changed')
    photo_region = body[0]
    card_count = photo_region.count(b'class="field-card neon-panel"')
    sources = re.findall(rb'<img\b[^>]*\bsrc="([^"]+)"', photo_region)
    routes = re.findall(rb'<a class="field-card neon-panel" href="([^"]+)"', photo_region)
    required_webp = (
        b'/assets/zm-v3-farming.webp', b'/assets/zm-v3-genetics.webp',
        b'/assets/zm-v3-industry.webp', b'/assets/zm-v3-economy.webp',
    )
    required_new_webp = tuple(f'/assets/zm-field-{slug}.webp'.encode() for slug in SLUGS)
    required_routes = (
        b'/agriculture/', b'/research/', b'/industry/', b'/economy/',
    ) + tuple(f'/fields/{slug}/'.encode() for slug in SLUGS)
    if (card_count != 10 or len(sources) != 10 or len(set(sources)) != 10 or
            tuple(sources) != required_webp + required_new_webp or
            tuple(routes) != required_routes):
        raise RuntimeError('Release must contain ten original cards, ten unique routes and distinct first-party photos')
    for slug in SLUGS:
        art = new[f'assets/zm-field-{slug}.webp']
        if webp_dimensions(art) != (320, 200):
            raise RuntimeError('Unapproved WebP image or dimension: ' + slug)
        page_html = new[f'fields/{slug}/index.html']
        if (b'<h1 id="hero-title">' not in page_html or
                f'/assets/zm-field-{slug}.webp'.encode() not in page_html or
                f'https://zomorodmelal.ir/fields/{slug}/'.encode() not in page_html):
            raise RuntimeError('Dedicated topic page missing: ' + slug)
    return old, new


def protected_fingerprints():
    # Legacy sites may not have all optional subsite files. Preserve EVERY existing one.
    result = {}
    for name in PROTECTED:
        path = ROOT / name
        if path.exists() or path.is_symlink():
            result[name] = sha256(read_regular(path))
    if len(result) < 9:
        raise RuntimeError('Too few protected existing files')
    return result


def ensure_disk_space(old, new):
    # Account for all fifteen files, including the 12 newly created SVGs/pages.
    # The size formula includes a private copy of old files, temporary writes,
    # filesystem overhead, and enough headroom for exact rollback.
    copy_bytes = sum(len(old[name]) for name in FILES)
    copy_bytes += sum(len(new[name]) for name in FILES + CREATED)
    required = max(32 * 1024 * 1024, 4 * copy_bytes + 8 * 1024 * 1024)
    if BACKUP_ROOT.parent.is_symlink() or not BACKUP_ROOT.parent.is_dir():
        raise RuntimeError('Untrusted or missing backup parent directory')
    for directory in (ROOT, BACKUP_ROOT.parent):
        if shutil.disk_usage(directory).free < required:
            raise RuntimeError('Insufficient free disk for verified release and rollback: ' + str(directory))


def created_destination(name: str, create_parents: bool = False) -> Path:
    if name not in CREATED:
        raise RuntimeError('Path outside approved create allowlist')
    parent = ROOT
    for piece in Path(name).parts[:-1]:
        parent = parent / piece
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise RuntimeError('Untrusted target directory: ' + str(parent))
        if create_parents and not parent.exists():
            parent.mkdir(mode=0o755)
    path = ROOT / name
    if path.is_symlink():
        raise RuntimeError('Symlinked target: ' + str(path))
    return path


def audit_live_baseline() -> dict:
    """Zero-write baseline inspection. No staged upload, backup or release approval."""
    identity()
    for name in FILES:
        if git_blob(read_regular(ROOT / name)) != OLD_BLOBS[name]:
            raise RuntimeError('Live source differs from approved baseline: ' + name)
    photos = validate_legacy_images()
    for name in CREATED:
        target = created_destination(name)
        if target.exists() or target.is_symlink():
            raise RuntimeError('New destination already exists; refuse overwrite: ' + name)
    protected = protected_fingerprints()
    if BACKUP_ROOT.is_symlink() or BACKUP_ROOT.parent.is_symlink() or not BACKUP_ROOT.parent.is_dir():
        raise RuntimeError('Private backup location is not ready')
    # This is a conservative MINIMUM; full 15-file free-space calculation
    # is intentionally deferred to preflight(stage) once stage exists.
    free = min(shutil.disk_usage(path).free for path in (ROOT, BACKUP_ROOT.parent))
    if free < 32 * 1024 * 1024:
        raise RuntimeError('Insufficient free disk for release readiness')
    return {
        'status': 'READ_ONLY_BASELINE_READY',
        'source_files_matching': len(FILES),
        'legacy_photos_healthy': len(photos),
        'new_destinations_available': len(CREATED),
        'protected_existing_files': len(protected),
        'minimum_disk_free_bytes': free,
        'stage_hashes_verified': False,
        'deployment_authorized': False,
        'deployment_performed': False,
    }


def preflight(stage: Path):
    identity()
    old, new = candidates(stage)
    ensure_disk_space(old, new)
    before = {}
    for name in FILES:
        path = ROOT / name
        actual = read_regular(path)
        if sha256(actual) != sha256(old[name]):
            raise RuntimeError('Live source differs from last pinned release: ' + name)
        before[name] = {'old': sha256(actual), 'new': sha256(new[name]),
                        'mode': stat.S_IMODE(path.stat().st_mode)}
    if BACKUP_ROOT.is_symlink():
        raise RuntimeError('Untrusted backup directory')
    for name in CREATED:
        target = created_destination(name)
        if target.exists() or target.is_symlink():
            raise RuntimeError('New destination already exists; refuse overwrite: ' + name)
    return {'files': before, 'created': {name: sha256(new[name]) for name in CREATED},
            'protected': protected_fingerprints(), 'legacy': validate_legacy_images()}


def atomic(path: Path, data: bytes, mode: int):
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.zm-fields-', delete=False) as stream:
            temp = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()



def atomic_create(path: Path, data: bytes, mode: int) -> None:
    """Create-only publication. Refuse a concurrent owner file, never replace it.

    Hardlinking a completed same-directory temporary file to the final name is
    an atomic no-overwrite operation on the same filesystem. Any collision fails
    with FileExistsError, instead of the os.replace overwrite race.
    """
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.zm-fields-new-', delete=False) as stream:
            temp = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        os.link(temp, path)
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()

def release_dir(release_id: str) -> Path:
    if not re.fullmatch(r'fields-[0-9]{7,22}', release_id):
        raise RuntimeError('Invalid release identifier')
    return BACKUP_ROOT / release_id


@contextmanager
def exclusive():
    if BACKUP_ROOT.is_symlink() or BACKUP_ROOT.parent.is_symlink() or not BACKUP_ROOT.parent.is_dir():
        raise RuntimeError('Untrusted backup parent')
    lock_file = BACKUP_ROOT.parent / '.zomorod-fields-release.lock'
    if lock_file.is_symlink():
        raise RuntimeError('Untrusted release lock')
    with open(lock_file, 'a+b') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def backup(release: Path, before, old):
    release.mkdir(mode=0o700)
    for name in FILES:
        target = release / 'old' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic(target, old[name], 0o600)
        if sha256(read_regular(target)) != before['files'][name]['old']:
            raise RuntimeError('Backup read-back failed: ' + name)
    atomic(release / 'manifest.json', json.dumps(before, sort_keys=True).encode(), 0o600)


def load_backup(release: Path):
    if release.is_symlink() or not release.is_dir():
        raise RuntimeError('Missing private release backup')
    manifest = json.loads(read_regular(release / 'manifest.json'))
    if (set(manifest['files']) != set(FILES) or set(manifest.get('created', {})) != set(CREATED) or
            set(manifest.get('legacy', {})) != set(LEGACY_IMAGES)):
        raise RuntimeError('Unsafe release manifest')
    old = {name: read_regular(release / 'old' / name) for name in FILES}
    for name in FILES:
        if sha256(old[name]) != manifest['files'][name]['old']:
            raise RuntimeError('Corrupted release backup: ' + name)
    return manifest, old


def verify(release_id: str) -> None:
    identity()
    manifest, _ = load_backup(release_dir(release_id))
    if protected_fingerprints() != manifest['protected']:
        raise RuntimeError('Internal content changed during release')
    if validate_legacy_images() != manifest['legacy']:
        raise RuntimeError('Legacy card photos changed during release')
    for name in FILES:
        if sha256(read_regular(ROOT / name)) != manifest['files'][name]['new']:
            raise RuntimeError('Published file does not match approved candidate: ' + name)
    for name in CREATED:
        if sha256(read_regular(created_destination(name))) != manifest['created'][name]:
            raise RuntimeError('Created asset/page does not match approved candidate: ' + name)
    print('ZM_FIELDS_RELEASE=VERIFIED; REPLACED_FILES=3; CREATED_FILES=12; INTERNAL_FILES_UNTOUCHED=YES')


def restore(release_id: str) -> None:
    manifest, old = load_backup(release_dir(release_id))
    if protected_fingerprints() != manifest['protected']:
        raise RuntimeError('Protected content mismatch; refuse automated restore')
    # Precheck EVERY target before changing anything. Preserve concurrent owner edits.
    for name in FILES:
        if sha256(read_regular(ROOT / name)) not in (
                manifest['files'][name]['new'], manifest['files'][name]['old']):
            raise RuntimeError('Concurrent edit detected; refuse restore: ' + name)
    for name in CREATED:
        target = created_destination(name)
        if target.exists() or target.is_symlink():
            if sha256(read_regular(target)) != manifest['created'][name]:
                raise RuntimeError('Concurrent edit detected on created file; refuse restore: ' + name)
    # Restore old HTML first, before removing the six linked destination pages.
    for name in ('index.html', 'assets/zm-reference-v3.css', 'assets/zm-reference-v3.js'):
        if sha256(read_regular(ROOT / name)) == manifest['files'][name]['new']:
            atomic(ROOT / name, old[name], manifest['files'][name]['mode'])
    for name in CREATED:
        target = created_destination(name)
        if target.exists() or target.is_symlink():
            if sha256(read_regular(target)) != manifest['created'][name]:
                raise RuntimeError('Created file changed during rollback: ' + name)
            target.unlink()
    for name in FILES:
        if sha256(read_regular(ROOT / name)) != manifest['files'][name]['old']:
            raise RuntimeError('Post-rollback mismatch: ' + name)
    print('ZM_FIELDS_RELEASE=ROLLED_BACK_EXACTLY; CREATED_FILES_REMOVED=12')



def apply(stage: Path, release_id: str) -> None:
    with exclusive():
        manifest = preflight(stage)
        old, new = candidates(stage)
        release = release_dir(release_id)
        if release.exists() or release.is_symlink():
            raise RuntimeError('Release identifier already used')
        if BACKUP_ROOT.is_symlink():
            raise RuntimeError('Untrusted backup root')
        BACKUP_ROOT.mkdir(mode=0o700, exist_ok=True)
        backup(release, manifest, old)
        # Create all six destination pages and their SVGs BEFORE updating homepage.
        # Final HTML switch is the last step. Every file is hash-pinned.
        try:
            for name in CREATED:
                target = created_destination(name, create_parents=True)
                if target.exists() or target.is_symlink():
                    raise RuntimeError('Create destination already claimed: ' + name)
                atomic_create(target, new[name], 0o644)
            for name in ('assets/zm-reference-v3.js', 'assets/zm-reference-v3.css', 'index.html'):
                if sha256(read_regular(ROOT / name)) != manifest['files'][name]['old']:
                    raise RuntimeError('Changed since audit: ' + name)
                atomic(ROOT / name, new[name], manifest['files'][name]['mode'])
            verify(release_id)
        except BaseException:
            restore(release_id)
            raise
        print('ZM_FIELDS_RELEASE=APPLIED_AFTER_EXPLICIT_APPROVAL; CREATED_FILES=12')



def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 1 and args[0] == 'audit-live':
        print(json.dumps(audit_live_baseline(), sort_keys=True))
    elif len(args) == 2 and args[0] == 'check':
        result = preflight(Path(args[1]))
        print(json.dumps(result, sort_keys=True))
    elif len(args) == 4 and args[0] == 'apply' and args[3] == '--owner-approved':
        apply(Path(args[1]), args[2])
    elif len(args) == 3 and args[0] == 'rollback' and args[2] == '--owner-approved':
        identity()
        with exclusive():
            restore(args[1])
    elif len(args) == 2 and args[0] == 'verify':
        verify(args[1])
    else:
        raise SystemExit('Read-only: audit-live | check STAGE | verify RELEASE; owner-only: apply STAGE RELEASE --owner-approved | rollback RELEASE --owner-approved')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
