#!/usr/bin/env python3
"""Recheck five authentic F01-F05 authoring pilots, one rework per dispatcher tick."""
import argparse,fcntl,importlib.util,json,os,shutil
from pathlib import Path
def module(path,name):
 spec=importlib.util.spec_from_file_location(name,str(path))
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
def run(root,source):
 root=Path(root);source=Path(source)
 if not root.is_dir() or root.is_symlink() or source.is_symlink():
  raise ValueError("FIVE_CYCLE_BAD_ROOT")
 lock=root/"engineering-gaps/.five-publication.lock"
 lock.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 with lock.open("a+b") as handle:
  os.fchmod(handle.fileno(),0o600)
  try:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {"status":"busy"}
  if shutil.disk_usage(root).free<1024*1024*1024:return {"status":"disk_hold"}
  maker=module(source/"factory_build50_five_publications.py","five_cycle_maker")
  proto=module(source/"factory_build_50.py","five_cycle_proto")
  for fid,product in maker.PRODUCTS.items():
   home=root/"build-50"/product;target=root/"digital-products"/product
   try:
    state=proto.read(home/"state.json")
    manifest=proto.read(target/"manufacturing_manifest.json")
    archive=target/(product+"-internal-qa.zip")
    good=proto.verify_attempt(home,state,maker.plan(proto,fid)["source_snapshot_sha256"])
    good=good and archive.is_file() and not archive.is_symlink()
    good=good and proto.file_sha(archive)==manifest["artifact_sha256"]
   except (KeyError,OSError,TypeError,ValueError):good=False
   if not good:
    return {"status":"one_family_rework_executed","family_id":fid,
      "result":maker.build(root,fid)}
  return {"status":"five_technical_families_verified"}
if __name__=="__main__":
 a=argparse.ArgumentParser()
 a.add_argument("--factory-private",required=True)
 a.add_argument("--module-dir",required=True)
 args=a.parse_args()
 out=run(args.factory_private,args.module_dir)
 print("FIVE_PUBLICATION_CYCLE="+json.dumps(out,sort_keys=True))
