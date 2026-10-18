#!/usr/bin/env python3
"""Surgical 3D glass treatment for all 29 homepage row headers; no DOM or card edits."""
from __future__ import annotations
import hashlib
import json
import os
import pwd
import re
import sys
import tempfile
from pathlib import Path

HOME = Path('/home/zomorod2/public_html/index.html')
BACKUPS = Path('/home/zomorod2/.backups/zomorod-glass-row-headers-20261018')
STYLE_ID = 'zm-glass-row-headers-20261018'
STYLE = r'''<style id="zm-glass-row-headers-20261018">
/* All existing explanatory panels, one above each scrolling card row.
   Paint-only: preserve sizes, alignment, element count, transforms, timings,
   click/touch hit targets and the existing fixed photograph. */
body .orbit-shelf > .shelf-explanation {
  background:
    radial-gradient(ellipse 90% 160% at 6% -35%,
      rgba(218,255,226,.25) 0%,rgba(86,176,142,.09) 45%,transparent 76%),
    linear-gradient(146deg,
      rgba(51,126,99,.56) 0%,rgba(9,48,43,.71) 46%,
      rgba(5,26,32,.81) 100%) !important;
  border-color:rgba(255,222,143,.75) !important;
  outline:1px solid rgba(244,246,218,.36);
  outline-offset:-2px;
  box-shadow:
    inset 1px 1px 0 rgba(255,255,241,.49),
    inset -1px -2px 0 rgba(117,215,193,.22),
    inset 0 0 19px rgba(208,242,221,.075),
    0 13px 29px rgba(0,10,18,.31),
    0 28px 57px rgba(0,10,18,.22),
    0 0 20px rgba(237,202,104,.16);
  -webkit-backdrop-filter:blur(8px) saturate(1.22);
  backdrop-filter:blur(8px) saturate(1.22);
  transition:box-shadow .28s ease,border-color .28s ease,outline-color .28s ease;
}
body .orbit-shelf > .shelf-explanation .shelf-heading-line h3 {
  color:#fff0c5;
  text-shadow:0 1px 1px rgba(3,12,18,.88),0 0 12px rgba(255,215,128,.24);
}
body .orbit-shelf > .shelf-explanation > p {
  color:#f4f5e8;
  text-shadow:0 1px 3px rgba(0,9,13,.78);
}
@media (hover:hover) and (pointer:fine){
  body .orbit-shelf > .shelf-explanation:hover {
    border-color:rgba(255,236,180,.92) !important;
    outline-color:rgba(255,243,211,.67);
    box-shadow:
      inset 1px 1px 0 rgba(255,255,244,.58),
      inset -1px -2px 0 rgba(135,236,207,.27),
      0 17px 37px rgba(0,9,16,.35),
      0 31px 60px rgba(0,9,16,.25),
      0 0 26px rgba(250,208,111,.31);
  }
}
@media (max-width:700px){
  body .orbit-shelf > .shelf-explanation {
    -webkit-backdrop-filter:blur(3px) saturate(1.12);
    backdrop-filter:blur(3px) saturate(1.12);
  }
}
@media (prefers-reduced-motion:reduce){
  body .orbit-shelf > .shelf-explanation{transition:none !important}
}
</style>
'''

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def run_dir(run: str) -> Path:
    if not re.fullmatch(r'[0-9]{1,20}', run):
        raise RuntimeError('Invalid GitHub run ID')
    return BACKUPS / run

def safety() -> None:
    if pwd.getpwuid(os.getuid()).pw_name != 'zomorod2':
        raise RuntimeError('Wrong hosting identity')
    if not HOME.is_file() or HOME.is_symlink() or HOME.parent.is_symlink():
        raise RuntimeError('Unsafe live homepage path')
    if BACKUPS.is_symlink():
        raise RuntimeError('Unsafe backup path')

def transform(old: bytes) -> bytes:
    src = old.decode('utf-8')
    if len(old) < 1500000 or src.count('</head>') != 1 or src.count('</body>') != 1:
        raise RuntimeError('Unexpected HTML structure or truncated homepage')
    if 'id="' + STYLE_ID + '"' in src:
        raise RuntimeError('This glass row header patch is already installed')
    for needle in (
        'id="zm-fixed-scientific-background-20261018"',
        'id="zm-glass-floating-cards-20261018"',
        'id="orbital-cards"', 'id="solar-stage"', 'id="site-footer"',
        'ZOMOROD_ORBIT_DATA', '.shelf-explanation', '.shelf-heading-line',
        '.topic-card', '.card-track'
    ):
        if needle not in src:
            raise RuntimeError('Required live feature missing: ' + needle)
    updated = src.replace('</head>', STYLE + '</head>', 1).encode('utf-8')
    if updated.replace(STYLE.encode('utf-8'), b'', 1) != old:
        raise RuntimeError('HTML/data not preserved')
    return updated

def atomic(path: Path, data: bytes, mode: int) -> None:
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.zm-row-glass-',
                                         delete=False) as f:
            tmp = Path(f.name)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()

def selftest() -> None:
    sample = ('<html><head></head><body><main id="content">'
              '<div id="solar-stage"></div><div id="orbital-cards"></div>'
              '<style>.shelf-explanation{}.shelf-heading-line{}.topic-card{}.card-track{}</style>'
              '<footer id="site-footer"></footer><script>ZOMOROD_ORBIT_DATA</script>'
              '<style id="zm-fixed-scientific-background-20261018"></style>'
              '<style id="zm-glass-floating-cards-20261018"></style>'
              '</main></body></html>' + 'x' * 1600000).encode('utf-8')
    output = transform(sample)
    assert output.replace(STYLE.encode('utf-8'), b'', 1) == sample
    assert output.count(STYLE_ID.encode('utf-8')) == 1
    assert all(part in STYLE for part in
               ('backdrop-filter', '.shelf-explanation',
                'prefers-reduced-motion', 'box-shadow', 'pointer:fine'))
    assert not re.search(r'(?<![-\w])(width|height|padding|margin|transform|'
                         r'position|animation|display|flex|grid-template-columns)\s*:', STYLE)
    assert '.card-track{' not in STYLE and '.topic-card{' not in STYLE
    print('ROW_GLASS_SELFTEST_PASS=yes', flush=True)

def apply(run: str, expected: str) -> None:
    safety()
    if not re.fullmatch(r'[a-f0-9]{64}', expected):
        raise RuntimeError('Invalid expected homepage SHA256')
    before = HOME.read_bytes()
    if digest(before) != expected:
        raise RuntimeError('Homepage changed; refusing concurrent overwrite')
    after = transform(before)
    path = run_dir(run)
    if path.exists() or path.is_symlink():
        raise RuntimeError('Backup path already exists')
    path.mkdir(parents=True, mode=0o700)
    mode = HOME.stat().st_mode & 0o777
    atomic(path / 'index.before.html', before, 0o600)
    if digest((path / 'index.before.html').read_bytes()) != expected:
        raise RuntimeError('Backup verification failed')
    metadata = {'before':expected, 'after':digest(after), 'mode':mode}
    (path / 'manifest.json').write_text(json.dumps(metadata), encoding='utf-8')
    if digest(HOME.read_bytes()) != expected:
        raise RuntimeError('Concurrent homepage update before installation')
    atomic(HOME, after, mode)
    if digest(HOME.read_bytes()) != metadata['after']:
        raise RuntimeError('Post-install homepage digest mismatch')
    print('ROW_GLASS_PUBLISHED=yes', flush=True)
    print('ROW_GLASS_SHA256=' + metadata['after'], flush=True)

def verify(run: str) -> None:
    safety()
    path = run_dir(run)
    info = json.loads((path / 'manifest.json').read_text())
    before = (path / 'index.before.html').read_bytes()
    current = HOME.read_bytes()
    if digest(before) != info['before'] or digest(current) != info['after']:
        raise RuntimeError('Unexpected current or saved digest')
    if current.replace(STYLE.encode('utf-8'), b'', 1) != before:
        raise RuntimeError('Some original content was changed')
    print('ROW_GLASS_CSS_ONLY_VERIFIED=yes', flush=True)

def rollback(run: str) -> None:
    safety()
    path = run_dir(run)
    if not (path / 'manifest.json').is_file():
        print('ROW_GLASS_NO_INSTALL_TO_RESTORE=yes', flush=True)
        return
    info = json.loads((path / 'manifest.json').read_text())
    before = (path / 'index.before.html').read_bytes()
    if digest(before) != info['before']:
        raise RuntimeError('Backup corruption')
    present = digest(HOME.read_bytes())
    if present == info['before']:
        print('ROW_GLASS_ORIGINAL_ALREADY_PRESENT=yes', flush=True)
        return
    if present != info['after']:
        raise RuntimeError('Another update present; refusing to overwrite')
    atomic(HOME, before, info['mode'])
    if digest(HOME.read_bytes()) != info['before']:
        raise RuntimeError('Rollback verification failed')
    print('ROW_GLASS_PREVIOUS_HOMEPAGE_RESTORED=yes', flush=True)

if __name__ == '__main__':
    if sys.argv[1:] == ['selftest']:
        selftest()
    elif len(sys.argv) == 4 and sys.argv[1] == 'apply':
        apply(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == 'verify':
        verify(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    else:
        raise SystemExit('selftest | apply RUN_ID SHA256 | verify RUN_ID | rollback RUN_ID')
