#!/usr/bin/env python3
"""Read-only source audit of the ORIGINAL Living Cities cPanel browser release.

This script never runs the game, reads secrets, mutates saves, or publishes.
It is intended to run as the site's own cPanel user via an approved terminal
or the existing fingerprint-pinned GitHub -> VPS -> host relay.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import sys


HOME = Path('/home/zomorod2')
ORIGINAL_RELEASE = HOME / '.private/living-cities-app/releases/b3fe1b772368f3f0874481ab88ad82862bd24de2'
PUBLIC = HOME / 'public_html/living-cities'
EXPECTED = {
    'html': 'play/index.html',
    'entry': 'static/living_cities/app.mjs',
    'renderer': 'static/living_cities/render.mjs',
    'style': 'static/living_cities/style.css',
}
HIDE_PATTERNS = {
    'inline_display_none': re.compile(r'(?:id=[\"\']world[\"\'][^>]{0,160}display\s*:\s*none|display\s*:\s*none[^>]{0,160}id=[\"\']world[\"\'])', re.I),
    'runtime_hide': re.compile(r'\b(?:world|canvas|renderer)\b.{0,120}(?:style\.display\s*=\s*[\"\']none|\.hidden\s*=\s*true)', re.I),
    'webgl_branch': re.compile(r'\b(?:webgl2?|webglrenderer|contextlost|context-lost)\b', re.I),
}


def file_evidence(folder: Path, relative: str):
    path = folder / relative
    if path.is_symlink() or not path.is_file():
        return {'exists': False, 'symlink_rejected': path.is_symlink()}
    if path.stat().st_size > 2_000_000:
        return {'exists': True, 'oversized': True, 'size': path.stat().st_size}
    content = path.read_bytes()
    text = content.decode('utf-8', errors='replace')
    return {
        'exists': True,
        'size': len(content),
        'sha256': hashlib.sha256(content).hexdigest(),
        'signals': {
            name: [index for index, line in enumerate(text.splitlines(), 1) if regex.search(line)][:15]
            for name, regex in HIDE_PATTERNS.items()
        },
        'contains_world_canvas': bool(re.search(r'<canvas\b[^>]*\bid=[\"\']world[\"\']', text, re.I)),
        'contains_3d_renderer': bool(re.search(r'\b(?:WebGLRenderer|THREE\.Scene|webgl2?)\b', text, re.I)),
    }


def audit(folder: Path):
    evidence = {name: file_evidence(folder, relative) for name, relative in EXPECTED.items()}
    issues = [f'missing_{name}' for name, item in evidence.items() if not item.get('exists')]
    if not evidence['html'].get('contains_world_canvas'):
        issues.append('missing_html_world_canvas')
    if evidence['html'].get('signals', {}).get('inline_display_none'):
        issues.append('html_hides_world_canvas')
    if evidence['entry'].get('signals', {}).get('runtime_hide'):
        issues.append('entry_has_canvas_hide_branch_review_required')
    if evidence['renderer'].get('signals', {}).get('runtime_hide'):
        issues.append('renderer_has_canvas_hide_branch_review_required')
    return {'scope': str(folder), 'assets': evidence, 'issues': issues,
            'note': 'Static evidence only; runtime WebGL availability and JS errors require a browser trace.'}


def main():
    if len(sys.argv) != 1:
        raise SystemExit('no parameters accepted; production path is fixed')
    if os.geteuid() != HOME.stat().st_uid:
        raise SystemExit('ERROR: requires original cPanel owner')
    if PUBLIC.is_symlink() or not PUBLIC.is_dir():
        raise SystemExit('ERROR: live original release path unavailable or is a symlink')
    if ORIGINAL_RELEASE.is_symlink():
        raise SystemExit('ERROR: private original source path is a symlink')
    result = audit(PUBLIC)
    result['original_source_release_exists'] = ORIGINAL_RELEASE.is_dir()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['issues']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
