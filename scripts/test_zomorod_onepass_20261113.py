#!/usr/bin/env python3
"""Isolated finite one-pass install/rollback regression. No network or site writes."""
import importlib.util, json, sys, tempfile
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    repo=Path(__file__).resolve().parents[1]
    script=repo/'scripts/zomorod_onepass_guarded_20261113.py'
    spec=importlib.util.spec_from_file_location('guard_zm_once',script)
    g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    if len(args)!=1:raise SystemExit('Pass old/new stage root')
    stage=Path(args[0]).resolve()
    with tempfile.TemporaryDirectory() as directory:
     home=Path(directory)
     site=home/'public_html';(site/'assets').mkdir(parents=True)
     backups=home/'backups/zomorod-vision-onepass-20261113';backups.parent.mkdir()
     for rel in g.REPLACE:
      target=site/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((stage/'old'/rel).read_bytes())
     for rel in g.PROTECTED:
      target=site/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(('protected unchanged '+rel).encode())
     old_digest={rel:sha256((site/rel).read_bytes()).hexdigest() for rel in g.PROTECTED}
     with patch.multiple(g,ROOT=site,STAGE=stage,BACKUP_ROOT=backups,LOCK=backups.parent/'lock'),patch.object(g,'root_guard',lambda:None):
      manifest=g.preflight();assert len(manifest['replace'])==3 and len(manifest['create'])==2
      g.apply('vision-8452210');g.verify('vision-8452210')
      for rel in g.CREATE:assert (site/rel).is_file()
      assert all(sha256((site/rel).read_bytes()).hexdigest()==old_digest[rel] for rel in g.PROTECTED)
      try:g.preflight()
      except RuntimeError:pass
      else:raise AssertionError('Repeat release incorrectly authorized')
      g.rollback('vision-8452210')
      assert not (site/'ar').exists()
      for rel in g.CREATE:assert not (site/rel).exists()
      for rel in g.REPLACE:assert (site/rel).read_bytes()==(stage/'old'/rel).read_bytes()
      assert all(sha256((site/rel).read_bytes()).hexdigest()==old_digest[rel] for rel in g.PROTECTED)
      (site/'index.html').write_bytes(b'other owner edit')
      try:g.preflight()
      except RuntimeError:pass
      else:raise AssertionError('Unexpected concurrent revision accepted')
    print('ZM_ONEPASS_ISOLATED_INSTALL_VERIFY_ROLLBACK_AND_CONCURRENT_GUARD=PASS')

if __name__ == "__main__":
    main()
