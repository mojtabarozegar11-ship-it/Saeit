#!/usr/bin/env python3
"""Bounded periodic recheck for four real technical media/art portfolios."""
import argparse,fcntl,importlib.util,json,os,shutil
from pathlib import Path
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,str(path))
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def cycle(root,module_dir):
 root=Path(root);module_dir=Path(module_dir)
 if root.is_symlink() or not root.is_dir() or module_dir.is_symlink():raise ValueError('NEXT4_ROOT')
 lock=root/'engineering-gaps/.next4-cycle.lock'
 lock.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 with lock.open('a+b') as f:
  os.fchmod(f.fileno(),0o600)
  try:fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'status':'busy'}
  if shutil.disk_usage(root).free<1024*1024*1024:return {'status':'resource_hold'}
  maker=load('next4_cyclical_maker',module_dir/'factory_build50_next4_media.py')
  proto=load('next4_cyclical_proto',module_dir/'factory_build_50.py')
  for family,product in maker.PRODUCTS.items():
   home=root/'build-50'/product
   try:
    state=proto.read(home/'state.json')
    manifest=proto.read(root/'digital-products'/product/'manufacturing_manifest.json')
    archive=root/'digital-products'/product/(product+'-internal-qa.zip')
    plan=maker.plan(proto,family)
    proven=proto.verify_attempt(home,state,plan['source_snapshot_sha256'])
    proven=proven and archive.is_file() and not archive.is_symlink() and maker.sha(archive)==manifest['artifact_sha256']
   except (OSError,KeyError,ValueError,TypeError):proven=False
   if not proven:
    result=maker.build(root,family)
    return {'status':'one_family_attempted','family':family,'build_result':result['status']}
  return {'status':'four_original_technical_products_reverified','families':4}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--factory-private',required=True)
 p.add_argument('--module-dir',required=True);a=p.parse_args()
 result=cycle(a.factory_private,a.module_dir)
 print('FACTORY_NEXT4_PERIODIC='+json.dumps(result,sort_keys=True))
 if result.get('build_result')=='technical_rework_required':raise SystemExit(2)
