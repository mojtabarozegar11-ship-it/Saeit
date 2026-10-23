#!/usr/bin/env python3
"""Verify additive HTML upgrade does not disturb the existing 3D game."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

source = Path(__file__).with_name('nexus-upgrade.py')
spec = spec_from_file_location('nexus_upgrade', source)
module = module_from_spec(spec)
spec.loader.exec_module(module)
before = ('''<!doctype html><html><body><!-- ZM-ARROW-ESCAPE-THIRD-CARD-20261022 -->
<section class="intro"><h1>مکعب پیکان‌ها</h1></section>
<div class="game-frame"><div id="cubeStage"></div></div>
<script src="./cube-engine.js?v=maze3d-v4"></script>
<script src="./app.js?v=maze3d-v4"></script></body></html>''').encode()
after = module.update_index(before)
assert before != after
assert after.count(module.MARK.encode()) == 1
assert b'href="./nexus.html"' in after
assert module.update_index(after) == after, 'a second deployment must not duplicate the link'
assert after.decode().replace(module.CTA, '', 1) == before.decode()
for marker in (b'cubeStage', b'cube-engine.js', b'maze3d-v4', b'game-frame'):
    assert before.count(marker) == after.count(marker), f'old gameplay mutated: {marker}'
print('NEXUS_ADDITIVE_LIVE_UPGRADE_QA=PASS')
