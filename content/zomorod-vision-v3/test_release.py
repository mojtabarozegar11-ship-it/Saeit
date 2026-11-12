#!/usr/bin/env python3
"""Local write-safety tests. NEVER connects to the real site or servers."""
import importlib.util
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from hashlib import sha256
source=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('zv3_deploy',source/'deploy_guarded.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
assert len(mod.candidate()['art'])==17
with tempfile.TemporaryDirectory(prefix='zm-ref-qa-') as td:
 base=Path(td);site=base/'public_html';site.mkdir();(site/'assets').mkdir()
 for asset in ('static/site/zomorod-v7/company-logo.webp','static/site/heroes/ai.webp'):
  path=site/asset;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'RIFF0000WEBP')
 legacy=('<body class="nexus-home">'+'previous homepage '*1800).encode()
 archive=b'legacy pre NEXUS 20261112'
 (site/'index.html').write_bytes(legacy)
 old=site/'site-heritage/home-before-nexus-20261112/index.html';old.parent.mkdir(parents=True,exist_ok=True);old.write_bytes(archive)
 for path in mod.PROTECTED:
  f=site/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('Protected: '+path)
 backups=base/'.backups/zm';backups.parent.mkdir()
 with patch.multiple(mod,SITE=site,BACKUPS=backups,LOCK=base/'.backups/lock',HOME=site/'index.html',CSS=site/'assets/zm-reference-v3.css',JS=site/'assets/zm-reference-v3.js',OLD_ARCHIVE=old,EXPECTED_CURRENT_SHA=sha256(legacy).hexdigest(),EXPECTED_ARCHIVE_SHA=sha256(archive).hexdigest()),patch.object(mod,'identity',lambda:None):
  original_hashes=mod.protected_hashes()
  pre=mod.preflight()
  assert pre['candidate']==sha256((source/'index.html').read_bytes()).hexdigest()
  mod.apply('vision-1001')
  mod.verify('vision-1001')
  assert mod.protected_hashes()==original_hashes
  assert len(list((site/'assets').glob('zm-v3-*.webp')))==17
  try:mod.preflight()
  except RuntimeError:pass
  else:raise AssertionError('Duplicate publication was not blocked')
  mod.rollback('vision-1001')
  assert site.joinpath('index.html').read_bytes()==legacy
  assert not site.joinpath('assets/zm-reference-v3.css').exists()
  assert not site.joinpath('assets/zm-reference-v3.js').exists()
  assert not list((site/'assets').glob('zm-v3-*.webp'))
  assert mod.protected_hashes()==original_hashes
  assert old.read_bytes()==archive
  assert backups.joinpath('vision-1001/home.before.html').read_bytes()==legacy
  print('VISION_V3_ATOMIC_INSTALL_VERIFY_ROLLBACK=PASS')
  print('VISION_V3_PROTECTED_PAGES_AND_ARCHIVE=UNCHANGED')