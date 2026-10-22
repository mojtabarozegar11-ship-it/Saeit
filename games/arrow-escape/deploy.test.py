#!/usr/bin/env python3
"""Offline test of exact card insertion and immutable unrelated rows."""
import copy
import importlib.util
import json
from pathlib import Path

source = Path(__file__).with_name('deploy.py')
spec = importlib.util.spec_from_file_location('arrow_deploy', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

rows = []
for i in range(27):
    row = {
        'id': f'ZM-R{i:02}', 'index': i, 'slug': 'digital-services' if i == 25 else f'row-{i}',
        'title': 'فناوری اطلاعات و خدمات دیجیتال' if i == 25 else f'سطر {i}',
        'cards': [{'id': f'TEST-R{i}-C1', 'slug': 'other-card'}]
    }
    rows.append(row)
target = rows[25]
target['cards'] = [
    {'id': 'ZM-R25-GAME-FARM-DOMINION-20261019', 'slug': 'farm-dominion-3d'},
    {'id': 'ZM-R25-GAME-RAMADAN-WAR-20261022', 'slug': 'ramadan-war'},
    {'id': 'ZM-R25-C01', 'slug': 'website-design'}
] + [{'id': f'ZM-R25-C{i:02}', 'slug': f'card-{i}'} for i in range(2, 22)]
before = copy.deepcopy(rows)
original_json = json.dumps({'rows': rows}, ensure_ascii=False, separators=(',', ':'))
html = ('<!doctype html><html><body><script>window.ZOMOROD_ORBIT_DATA=' +
        original_json + ';</script></body></html>').encode()
result = module.edit_home(html)
assert result != html
assert html.decode().replace(original_json, '') == result.decode().replace(
    module.PATTERN.search(result.decode()).group(2), '')
after = json.loads(module.PATTERN.search(result.decode()).group(2))['rows']
assert len(after[25]['cards']) == 24
assert after[25]['cards'][2]['id'] == module.GAME_ID
assert after[25]['cards'][2]['canonicalUrl'] == '/arrow-escape/'
assert after[25]['cards'][:2] == before[25]['cards'][:2]
assert after[25]['cards'][3:] == before[25]['cards'][2:]
assert after[:25] == before[:25] and after[26:] == before[26:]
print('ARROW_CARD_3_ISOLATION=PASS')
