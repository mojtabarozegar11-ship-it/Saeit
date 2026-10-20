#!/usr/bin/env python3
"""Five-minute private F15 rebuild only when independent proofs are missing."""
import argparse,fcntl,importlib.util,json,os,shutil
from pathlib import Path
def load(path,name):
 sp=importlib.util.spec_from_file_location(name,str(path))
 m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def run(root,modules):
 root=Path(root);modules=Path(modules)
 if root.is_symlink() or not root.is_dir() or modules.is_symlink():
  raise ValueError('F15_CYCLE_BAD_ROOT')
 lock=root/'engineering-gaps/.f15-assets.lock'
 lock.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 with lock.open('a+b') as f:
  os.fchmod(f.fileno(),0o600)
  try:fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'status':'busy'}
  if shutil.disk_usage(root).free<1024*1024*1024:return {'status':'disk_hold'}
  maker=load(modules/'factory_build50_f15_game_assets.py','f15_live_maker')
  proto=load(modules/'factory_build_50.py','f15_live_build50')
  home=root/'build-50'/maker.PRODUCT;target=root/'digital-products'/maker.PRODUCT
  try:
   state=proto.read(home/'state.json')
   manifest=proto.read(target/'manufacturing_manifest.json')
   archive=target/(maker.PRODUCT+'-internal-qa.zip')
   valid=proto.verify_attempt(home,state,maker.plan(proto)['source_snapshot_sha256'])
   valid=valid and archive.is_file() and not archive.is_symlink() and maker.sha(archive)==manifest['artifact_sha256']
  except (ValueError,OSError,KeyError,TypeError):valid=False
  if valid:return {'status':'technical_product_reverified','family':'F15'}
  result=maker.build(root)
  return {'status':'technical_product_build_attempted','family':'F15','builder_status':result['status']}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--factory-private',required=True)
 p.add_argument('--module-dir',required=True);a=p.parse_args()
 result=run(a.factory_private,a.module_dir)
 print('FACTORY_F15_PERIODIC='+json.dumps(result,sort_keys=True))
 if result.get('builder_status')=='technical_rework_required':raise SystemExit(2)
