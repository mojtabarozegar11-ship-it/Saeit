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
    slugs = mod.SLUGS
    core = (
        [('/agriculture/', '/assets/zm-v3-farming.webp'),
         ('/research/', '/assets/zm-v3-genetics.webp'),
         ('/industry/', '/assets/zm-v3-industry.webp'),
         ('/economy/', '/assets/zm-v3-economy.webp')]
        + [(f'/fields/{slug}/', f'/assets/zm-field-{slug}.svg') for slug in slugs]
    )
    field_html = (
        b'data-auto-strip=\n' * 3 +
        b'<div id="fields-carousel" data-field-carousel="fields-carousel">' +
        b''.join(
            f'<a class="field-card neon-panel" href="{href}"><img src="{source}"></a>'.encode()
            for href, source in core
        ) +
        b'</div><button class="auto-rotator-toggle fields-rotator-toggle" data-rotator-toggle="fields-carousel"></button>' +
        b'data-rotator-toggle=\n' * 3 +
        b'zm-reference-v3.js?v=20261113-fields1\nzm-reference-v3.css?v=20261113-fields1\n'
    )
    new = {
        'index.html': field_html,
        'assets/zm-reference-v3.css': b'new CSS for layout',
        'assets/zm-reference-v3.js': b'const strips=Array.from(document.querySelectorAll(\nprefers-reduced-motion',
    }
    for slug in slugs:
        new[f'assets/zm-field-{slug}.svg'] = (
            b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 750" width="1200" height="750"></svg>'
        )
        new[f'fields/{slug}/index.html'] = (
            f'<html><h1 id="hero-title">{slug}</h1><img src="/assets/zm-field-{slug}.svg">'
            f'<link rel="canonical" href="https://zomorodmelal.ir/fields/{slug}/"></html>'
        ).encode()
    for name in mod.FILES:
        (root / name).write_bytes(old[name])
        (stage / 'old' / name).write_bytes(old[name])
    for name in mod.FILES + mod.CREATED:
        dest = stage / 'new' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(new[name])

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
    assert len(manifest['files']) == 3 and len(manifest['created']) == 12 and len(manifest['protected']) >= 9
    assert not mod.BACKUP_ROOT.exists(), 'Read-only check must not make backups'
    mod.apply(stage, 'fields-1234567')
    mod.verify('fields-1234567')
    assert all((root / x).read_bytes() == new[x] for x in mod.FILES + mod.CREATED)
    mod.restore('fields-1234567')
    assert all((root / x).read_bytes() == old[x] for x in mod.FILES)
    assert all(not (root / x).exists() for x in mod.CREATED)


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


def test_disk_space_guard_refuses_to_touch_live_or_create_backups(sandbox, monkeypatch):
    from types import SimpleNamespace

    root, stage, old, new = sandbox
    monkeypatch.setattr(mod.shutil, 'disk_usage', lambda path: SimpleNamespace(free=0))
    with pytest.raises(RuntimeError, match='Insufficient free disk'):
        mod.preflight(stage)
    assert not mod.BACKUP_ROOT.exists()
    assert all((root / x).read_bytes() == old[x] for x in mod.FILES)


def test_disk_space_guard_allows_sufficient_space(sandbox, monkeypatch):
    from types import SimpleNamespace

    root, stage, old, new = sandbox
    monkeypatch.setattr(mod.shutil, 'disk_usage', lambda path: SimpleNamespace(free=128 * 1024 * 1024))
    manifest = mod.preflight(stage)
    assert len(manifest['files']) == 3
    assert not mod.BACKUP_ROOT.exists()


def test_carousel_workflow_has_no_production_job():
    workflow = (SOURCE.parents[1] / '.github/workflows/zomorod-onepass-full-20261113.yml').read_text()
    assert '\n  pull_request:\n' in workflow
    assert '\n  push:\n' not in workflow
    assert '\n  workflow_dispatch:\n' not in workflow
    assert '\n  publish:\n' not in workflow
    assert '\n  public-browser:\n' not in workflow
    assert '\n  rollback-after-browser-failure:\n' not in workflow
    assert workflow.count('\n  validate-and-visual:\n') == 1
    assert "      - 'scripts/zomorod_fields_guard_20261113.py'" in workflow
    assert "      - 'tests/test_zomorod_fields_release_guard.py'" in workflow
    assert '  contents: read' in workflow
    assert '  cancel-in-progress: true' in workflow
    assert '  group: ${{ github.workflow }}-pr-${{ github.event.pull_request.number }}' in workflow


def test_rejects_four_originals_even_if_js_would_clone(sandbox):
    root, stage, old, new = sandbox
    source = (stage / 'new' / 'index.html').read_bytes()
    import re
    shortened = re.sub(rb'(<a class="field-card neon-panel"[^>]*>.*?</a>){6}', b'', source, count=1)
    assert shortened != source
    (stage / 'new' / 'index.html').write_bytes(shortened)
    mod.NEW_BLOBS['index.html'] = mod.git_blob(shortened)
    with pytest.raises(RuntimeError, match='ten original cards'):
        mod.preflight(stage)


def test_rejects_ten_cards_with_repeated_images(sandbox):
    root, stage, old, new = sandbox
    source = (stage / 'new' / 'index.html').read_bytes()
    repeated = source.replace(b'zm-field-games-simulation.svg', b'zm-field-smart-tools.svg')
    (stage / 'new' / 'index.html').write_bytes(repeated)
    mod.NEW_BLOBS['index.html'] = mod.git_blob(repeated)
    with pytest.raises(RuntimeError, match='distinct first-party photos'):
        mod.preflight(stage)


def test_refuse_collision_with_existing_owner_page(sandbox):
    root, stage, old, new = sandbox
    existing = root / mod.CREATED[0]
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b'pre-existing owner content')
    with pytest.raises(RuntimeError, match='already exists'):
        mod.preflight(stage)
    assert existing.read_bytes() == b'pre-existing owner content'
    assert all((root / name).read_bytes() == old[name] for name in mod.FILES)


def test_refuse_rollback_if_new_page_was_changed_by_owner(sandbox):
    root, stage, old, new = sandbox
    mod.apply(stage, 'fields-1234582')
    created = root / mod.CREATED[-1]
    created.write_bytes(b'owner updated page after publication')
    with pytest.raises(RuntimeError, match='Concurrent edit detected on created file'):
        mod.restore('fields-1234582')
    assert created.read_bytes() == b'owner updated page after publication'


def test_reject_missing_sixth_svg_or_unapproved_page(sandbox):
    root, stage, old, new = sandbox
    missing = stage / 'new' / mod.CREATED[5]
    missing.unlink()
    with pytest.raises(RuntimeError, match='Unexpected staged files'):
        mod.preflight(stage)
    missing.write_bytes(new[mod.CREATED[5]])
    unapproved = stage / 'new' / mod.CREATED[-1]
    unapproved.write_bytes(b'fake topic page')
    with pytest.raises(RuntimeError, match='Candidate not approved'):
        mod.preflight(stage)


def test_mid_publish_rollback_removes_all_created_assets(sandbox, monkeypatch):
    root, stage, old, new = sandbox
    atomic = mod.atomic
    def failing_on_css(path, data, mode):
        if path == root / 'assets/zm-reference-v3.css' and data == new['assets/zm-reference-v3.css']:
            raise OSError('injected CSS failure')
        return atomic(path, data, mode)
    monkeypatch.setattr(mod, 'atomic', failing_on_css)
    with pytest.raises(OSError, match='injected CSS failure'):
        mod.apply(stage, 'fields-1234583')
    assert all(not (root / p).exists() for p in mod.CREATED)
    assert all((root / name).read_bytes() == old[name] for name in mod.FILES)


def test_disk_budget_includes_all_twelve_created_files(sandbox, monkeypatch):
    from types import SimpleNamespace
    root, stage, old, new = sandbox
    # Artificially inflate just one of the created assets. The preflight should
    # reject under its larger 4x total-size safety budget.
    # Keep XML valid so the test reaches the disk-space check, not ET.ParseError.
    large = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 750"'
        b' width="1200" height="750"><!--' +
        b'Z' * (11 * 1024 * 1024) + b'--></svg>'
    )
    name = mod.CREATED[0]
    (stage / 'new' / name).write_bytes(large)
    monkeypatch.setitem(mod.NEW_BLOBS, name, mod.git_blob(large))
    monkeypatch.setattr(mod.shutil, 'disk_usage',
                        lambda _: SimpleNamespace(free=33 * 1024 * 1024))
    with pytest.raises(RuntimeError, match='Insufficient free disk'):
        mod.preflight(stage)
    assert all((root / path).read_bytes() == old[path] for path in mod.FILES)


def test_atomic_create_never_replaces_concurrent_owner_file(sandbox):
    root, stage, old, new = sandbox
    target = root / mod.CREATED[0]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b'owner placed image before release write')
    with pytest.raises(FileExistsError):
        mod.atomic_create(target, b'new released image bytes', 0o644)
    assert target.read_bytes() == b'owner placed image before release write'


def test_atomic_create_safely_writes_new_file(sandbox):
    root, stage, old, new = sandbox
    target = root / mod.CREATED[0]
    target.parent.mkdir(parents=True, exist_ok=True)
    mod.atomic_create(target, b'new released image bytes', 0o644)
    assert target.read_bytes() == b'new released image bytes'
    with pytest.raises(FileExistsError):
        mod.atomic_create(target, b'second write must fail', 0o644)
    assert target.read_bytes() == b'new released image bytes'
