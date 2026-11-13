"""No-network regression for pinned three-file carousel release and rollback."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/zomorod_fields_guard_20261113.py'
spec = importlib.util.spec_from_file_location('zm_fields_guard', SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    root = tmp_path / 'public_html'
    root.mkdir()
    (root / 'assets').mkdir()
    stage = tmp_path / 'staged'
    for sub in ('old', 'new'):
        (stage / sub / 'assets').mkdir(parents=True)
    old = {
        'index.html': b'prior homepage refs all1',
        'assets/zm-reference-v3.css': b'old CSS',
        'assets/zm-reference-v3.js': b'old JS',
    }
    new = {
        'index.html': b'data-auto-strip=\n' * 3 + b'data-field-carousel=\n' + b'data-rotator-toggle=\n' * 4 + b'zm-reference-v3.js?v=20261113-fields1\nzm-reference-v3.css?v=20261113-fields1\n',
        'assets/zm-reference-v3.css': b'new CSS for layout',
        'assets/zm-reference-v3.js': b'const strips=Array.from(document.querySelectorAll(\nprefers-reduced-motion',
    }
    for name in mod.FILES:
        (root / name).write_bytes(old[name])
        (stage / 'old' / name).write_bytes(old[name])
        (stage / 'new' / name).write_bytes(new[name])
    for name in mod.PROTECTED:
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(('unchanged: ' + name).encode())
    monkeypatch.setattr(mod, 'ROOT', root)
    monkeypatch.setattr(mod, 'BACKUP_ROOT', tmp_path / 'backups' / 'zm-fields')
    (tmp_path / 'backups').mkdir()
    monkeypatch.setattr(mod, 'identity', lambda: None)
    monkeypatch.setattr(mod, 'OLD_BLOBS', {k: mod.git_blob(v) for k, v in old.items()})
    monkeypatch.setattr(mod, 'NEW_BLOBS', {k: mod.git_blob(v) for k, v in new.items()})
    return root, stage, old, new


def test_exact_staging_read_only_then_verify_and_restore(sandbox):
    root, stage, old, new = sandbox
    manifest = mod.preflight(stage)
    assert len(manifest['files']) == 3 and len(manifest['protected']) >= 9
    assert not mod.BACKUP_ROOT.exists(), 'Read-only check must not make backups'
    mod.apply(stage, 'fields-1234567')
    mod.verify('fields-1234567')
    assert all((root / x).read_bytes() == new[x] for x in mod.FILES)
    mod.restore('fields-1234567')
    assert all((root / x).read_bytes() == old[x] for x in mod.FILES)


def test_concurrent_human_edit_refuses_rollback(sandbox):
    root, stage, old, new = sandbox
    mod.apply(stage, 'fields-1234568')
    (root / 'index.html').write_bytes(b'owner modified concurrently')
    with pytest.raises(RuntimeError, match='Concurrent edit'):
        mod.restore('fields-1234568')
    assert (root / 'index.html').read_bytes() == b'owner modified concurrently'


def test_changed_live_or_new_candidate_fails_closed(sandbox):
    root, stage, old, new = sandbox
    (root / 'index.html').write_bytes(b'concurrent live edit')
    with pytest.raises(RuntimeError, match='Live source differs'):
        mod.preflight(stage)
    (root / 'index.html').write_bytes(old['index.html'])
    (stage / 'new' / 'index.html').write_bytes(b'wrong candidate')
    with pytest.raises(RuntimeError, match='Candidate not approved'):
        mod.preflight(stage)


def test_no_implicit_publish_or_unapproved_rollback(sandbox):
    root, stage, old, new = sandbox
    with pytest.raises(SystemExit):
        mod.main(['apply', str(stage), 'fields-1234569'])
    with pytest.raises(SystemExit):
        mod.main(['rollback', 'fields-1234569'])
    assert not mod.BACKUP_ROOT.exists()
    assert all((root / x).read_bytes() == old[x] for x in mod.FILES)


def test_reject_extra_staged_files(sandbox):
    root, stage, old, new = sandbox
    (stage / 'new' / 'unexpected.txt').write_text('must reject')
    with pytest.raises(RuntimeError, match='Unexpected staged files'):
        mod.preflight(stage)


def test_mid_publish_failure_rolls_back_untouched_original(sandbox, monkeypatch):
    root, stage, old, new = sandbox
    atomic = mod.atomic
    fail_once = {'should_fail': True}

    def injecting_failure(path, data, mode):
        # Fail only a production candidate write, never the private backup.
        if path == root / 'assets/zm-reference-v3.css' and data == new['assets/zm-reference-v3.css'] and fail_once['should_fail']:
            fail_once['should_fail'] = False
            raise OSError('simulated interruption during CSS write')
        return atomic(path, data, mode)

    monkeypatch.setattr(mod, 'atomic', injecting_failure)
    with pytest.raises(OSError, match='simulated interruption'):
        mod.apply(stage, 'fields-1234570')
    assert all((root / x).read_bytes() == old[x] for x in mod.FILES)
    assert (mod.BACKUP_ROOT / 'fields-1234570' / 'manifest.json').is_file()


def test_preserve_protected_changes_and_reject_new_page_inside_root(sandbox):
    root, stage, old, new = sandbox
    mod.apply(stage, 'fields-1234571')
    protected = root / 'research/index.html'
    original = protected.read_bytes()
    protected.write_bytes(b'concurrent protected edit')
    with pytest.raises(RuntimeError, match='Internal content changed'):
        mod.verify('fields-1234571')
    with pytest.raises(RuntimeError, match='Protected content mismatch'):
        mod.restore('fields-1234571')
    assert protected.read_bytes() == b'concurrent protected edit'
    protected.write_bytes(original)
    mod.restore('fields-1234571')
    assert all((root / x).read_bytes() == old[x] for x in mod.FILES)


def test_staging_cannot_be_inside_public_html(sandbox):
    root, stage, old, new = sandbox
    bad_stage = root / 'unexpected-stage'
    for part in ('old', 'new'):
        for name in mod.FILES:
            dest = bad_stage / part / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((stage / part / name).read_bytes())
    with pytest.raises(RuntimeError, match='Stage cannot be inside public_html'):
        mod.preflight(bad_stage)
