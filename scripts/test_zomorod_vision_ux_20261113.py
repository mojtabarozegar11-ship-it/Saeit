#!/usr/bin/env python3
"""Offline/isolated test of the homepage UX patch. Never connects to hosting."""
import importlib.util
import sys
import tempfile
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch


def _run_cli():
    """Execute the staged regression only when invoked as a CLI script."""
    repo=Path(__file__).resolve().parents[1]
    source=repo/'scripts/zomorod_vision_ux_guarded_20261113.py'
    spec=importlib.util.spec_from_file_location('zm_ux_guard',source)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    oldref=sys.argv[1] if len(sys.argv)>1 else None
    if not oldref:raise SystemExit('Supply locally staged old/new release directory')
    stage=Path(oldref).resolve()
    with tempfile.TemporaryDirectory(prefix='zm-ux-safe-') as temporary:
     root=Path(temporary)
     site=root/'public_html'
     (site/'assets').mkdir(parents=True)
     for key in mod.FILES:
      p=site/key
      p.parent.mkdir(parents=True,exist_ok=True)
      p.write_bytes((stage/'old'/key).read_bytes())
     protected_names=mod.PROTECTED
     for name in protected_names:
      p=site/name
      p.parent.mkdir(parents=True,exist_ok=True)
      p.write_bytes(('Protected internal content '+name).encode())
     archive=site/'site-heritage/home-before-nexus-20261112/index.html'
     archive.parent.mkdir(parents=True)
     archive.write_bytes(b'immutable previous homepage for test')
     backups=root/'backup/vision-ux'
     backups.parent.mkdir()
     patched={key:site/key for key in mod.FILES}
     with patch.multiple(mod,SITE=site,STAGE=stage,BACKUPS=backups,LOCK=backups.parent/'lock',FILES=patched,ORIGINAL_ARCHIVE=archive),patch.object(mod,'identity',lambda:None):
      protected=mod.protected()
      checks=mod.preflight()
      assert len(checks['files'])==3
      mod.apply('ux-1042')
      mod.verify('ux-1042')
      assert mod.protected()==protected
      try:
       mod.preflight()
      except RuntimeError:
       pass
      else:
       raise AssertionError('Concurrent homepage revision was not refused')
      mod.rollback('ux-1042')
      assert mod.protected()==protected
      assert archive.read_bytes()==b'immutable previous homepage for test'
      assert all((site/key).read_bytes()==(stage/'old'/key).read_bytes() for key in mod.FILES)
      assert all((backups/'ux-1042'/'old'/key).read_bytes()==(stage/'old'/key).read_bytes() for key in mod.FILES)
      (site/'index.html').write_bytes(b'concurrent user edit')
      try:
       mod.preflight()
      except RuntimeError:
       pass
      else:
       raise AssertionError('Unexpected live revision was accepted')
      print('ZOMOROD_UX_BACKUP_APPLY_VERIFY_ROLLBACK_CONCURRENT_GUARD=PASS')
      print('ZOMOROD_UX_INNER_PAGES_UNCHANGED=PASS')


if __name__ == "__main__":
    _run_cli()
