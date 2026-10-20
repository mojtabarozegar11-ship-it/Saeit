#!/usr/bin/env python3
"""Recheck F24 and F35, at most one technical sample rebuild per tick."""
import argparse,fcntl,importlib.util,json,os,shutil
from pathlib import Path
def mod(path,name):
 s=importlib.util.spec_from_file_location(name,str(path))
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def run(root,module_dir):
 root=Path(root);module_dir=Path(module_dir)
 if not root.is_dir() or root.is_symlink() or module_dir.is_symlink():
  raise ValueError("GAP2_BAD_ROOT")
 p=root/"engineering-gaps/.commerce40-cad-prompt.lock"
 p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 with p.open("a+b") as lock:
  os.fchmod(lock.fileno(),0o600)
  try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {"status":"busy"}
  if shutil.disk_usage(root).free<1024*1024*1024:return {"status":"disk_hold"}
  proto=mod(module_dir/"factory_build_50.py","gap2_reconcile_proto")
  for family,filename in (("F24","factory_build50_f24_prompts.py"),("F35","factory_build50_f35_cad.py")):
   maker=mod(module_dir/filename,"gap2_reconcile_"+family)
   home=root/"build-50"/maker.PRODUCT
   target=root/"digital-products"/maker.PRODUCT
   try:
    state=proto.read(home/"state.json")
    manifest=proto.read(target/"manufacturing_manifest.json")
    archive=target/(maker.PRODUCT+"-internal-qa.zip")
    valid=proto.verify_attempt(home,state,maker.plan(proto)["source_snapshot_sha256"])
    valid=valid and archive.is_file() and not archive.is_symlink()
    valid=valid and maker.sha(archive)==manifest["artifact_sha256"]
   except (ValueError,OSError,KeyError,TypeError):valid=False
   if not valid:
    result=maker.build(root)
    return {"status":"one_rebuild","family":family,"outcome":result["status"]}
  return {"status":"both_products_verified","family_count":2}
if __name__=="__main__":
 ap=argparse.ArgumentParser()
 ap.add_argument("--factory-private",required=True)
 ap.add_argument("--module-dir",required=True)
 a=ap.parse_args();res=run(a.factory_private,a.module_dir)
 print("FACTORY_GAP2_PRIVATE_RECHECK="+json.dumps(res,sort_keys=True))
 if res.get("outcome")=="technical_rework_required":raise SystemExit(2)
