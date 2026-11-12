#!/usr/bin/env python3
"""Safe local end-to-end guardrail test; never touches the real domain or server."""
from __future__ import annotations
import importlib.util
import tempfile
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('zm_release',P/'deploy_guarded.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

with tempfile.TemporaryDirectory(prefix='zm-nexus-test-') as td:
    base=Path(td)
    site=base/'public_html';site.mkdir()
    (site/'assets').mkdir()
    (site/'site-heritage').mkdir()
    private=base/'.backups';private.mkdir()
    source=P
    legacy=('<!doctype html><html lang="fa" dir="rtl"><head></head><body><div id="main-view"></div><div id="orbital-cards"></div><footer id="site-footer"></footer><script>window.ZOMOROD_ORBIT_DATA={};</script></body></html>'+'z'*90000).encode()
    (site/'index.html').write_bytes(legacy)
    protected=[]
    for p in mod.PROTECTED[:7]:
        f=site/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('DO NOT MODIFY '+p)
        protected.append((f,sha256(f.read_bytes()).hexdigest()))
    for p in (
        'static/site/zomorod-v7/company-logo.webp',
        'static/site/heroes/smart-agriculture.webp','static/site/heroes/agriculture.webp',
        'static/site/heroes/research.webp','static/site/heroes/industry.webp',
        'static/site/heroes/economy.webp','static/site/heroes/ai.webp',
        'static/site/heroes/services.webp','static/site/heroes/marketplace.webp',
        'static/site/zomorod-ten-editorials/research.webp',
        'agriculture/assets/zomorod-olive-v1/laboratory.webp'
    ):
        f=site/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b'RIFF0000WEBP\x00')
    with patch.multiple(mod,SITE=site,BACKUPS=private/'nexus',SRC=source,HOME=site/'index.html',CSS=site/'assets/zm-nexus-v1.css',ARCHIVE=site/'site-heritage/home-before-nexus-20261112/index.html',LOCK=private/'.test-lock'),patch.object(mod,'ensure_identity',lambda:None):
        b=mod.preflight();assert b['original']==sha256(legacy).hexdigest()
        mod.apply('nexus-local-test')
        mod.verify('nexus-local-test')
        assert mod.ARCHIVE.read_bytes()==legacy
        for f,dig in protected:assert sha256(f.read_bytes()).hexdigest()==dig
        try:mod.preflight()
        except RuntimeError:pass
        else:raise AssertionError('Repeated install not blocked')
        mod.rollback('nexus-local-test')
        assert (site/'index.html').read_bytes()==legacy
        assert not (site/'assets/zm-nexus-v1.css').exists()
        for f,dig in protected:assert sha256(f.read_bytes()).hexdigest()==dig
        print('NEXUS_ATOMIC_APPLY_ROLLBACK_PROTECTED_FILES=PASS')