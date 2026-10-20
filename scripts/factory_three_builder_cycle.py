#!/usr/bin/env python3
"""Revalidate current actual three-family artifacts; at most one rebuild per tick."""
import argparse,fcntl,importlib.util,json,os,shutil
from pathlib import Path
def load(p,name):
 spec=importlib.util.spec_from_file_location(name,str(p))
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def cycle(root,module_dir):
 root=Path(root);module_dir=Path(module_dir)
 if root.is_symlink() or not root.is_dir() or module_dir.is_symlink():raise ValueError('THREE_CYCLE_ROOT_UNSAFE')
 lock=root/'engineering-gaps/.three-real-builders.lock'
 lock.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 with lock.open('a+b') as f:
  os.fchmod(f.fileno(),0o600)
  try:fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'status':'another_running'}
  if shutil.disk_usage(root).free<1024*1024*1024:return {'status':'disk_resource_hold'}
  maker=load(module_dir/'factory_build50_three_media.py','three_live_maker')
  proto=load(module_dir/'factory_build_50.py','three_live_proto')
  for family,product in maker.PRODUCTS.items():
   home=root/'build-50'/product
   try:
    state=proto.read(home/'state.json')
    manifest=proto.read(root/'digital-products'/product/'manufacturing_manifest.json')
    package=root/'digital-products'/product/(product+'-internal-qa.zip')
    plan=maker.task_plan(proto,family)
    good=proto.verify_attempt(home,state,plan['source_snapshot_sha256'])
    good=good and package.is_file() and not package.is_symlink() and maker.sha(package)==manifest['artifact_sha256']
   except (ValueError,OSError,KeyError,TypeError):good=False
   if not good:
    result=maker.build(root,family)
    return {'status':'one_product_attempted','family_id':family,'builder_result':result['status']}
  return {'status':'all_three_validated_current','families':3}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--factory-private',required=True)
 p.add_argument('--module-dir',required=True);a=p.parse_args()
 result=cycle(a.factory_private,a.module_dir)
 print('FACTORY_THREE_PERIODIC='+json.dumps(result,sort_keys=True))
 if result.get('builder_result')=='technical_rework_required':raise SystemExit(2)
