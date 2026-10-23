#!/usr/bin/env python3
"""Simulate an isolated release, concurrent edits, protected routes and rollback."""
import importlib.util
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'deploy_maze3d', Path(__file__).with_name('deploy_maze3d.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

with tempfile.TemporaryDirectory(prefix='zm-maze3d-test-') as temp:
    root = Path(temp) / 'public_html'
    game = root / 'arrow-escape'
    game.mkdir(parents=True)
    for route in ('index.html', 'agriculture/index.html', 'research/index.html'):
        page = root / route
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_bytes(b'Protected original page')
    stage = Path(temp) / 'stage'
    incoming = stage / 'incoming'
    incoming.mkdir(parents=True)
    source = Path(__file__).parent
    old = {}
    for name in m.FILES:
        old[name] = (b'ZM-ARROW-ESCAPE-THIRD-CARD-20261022 ' + m.OLD) if name == 'index.html' else b'old ' + name.encode()
        (game / name).write_bytes(old[name])
        (incoming / name).write_bytes((source / name).read_bytes())
    m.ROOT, m.GAME = root, game
    m.prepare(stage)
    original = (game / 'app.js').read_bytes()
    (game / 'app.js').write_bytes(b'concurrent')
    try:
        m.publish(stage, '12345')
        raise AssertionError('concurrent edit silently overwritten')
    except AssertionError as exc:
        assert 'concurrent edit' in str(exc)
    (game / 'app.js').write_bytes(original)
    protected = root / 'agriculture/index.html'
    protected.write_bytes(b'concurrent protected')
    try:
        m.publish(stage, '12345')
        raise AssertionError('protected page changed without abort')
    except AssertionError as exc:
        assert 'unrelated route' in str(exc)
    protected.write_bytes(b'Protected original page')
    m.publish(stage, '12345')
    m.verify(stage)
    for name in m.FILES:
        assert (game / name).read_bytes() == (source / name).read_bytes()
    m.rollback(stage, '12345')
    for name in m.FILES:
        assert (game / name).read_bytes() == old[name]
print('ARROW_MAZE3D_SAFE_RELEASE_AND_ROLLBACK=PASS')
