"""Preserve missing pure V91 agent-policy code into private MojPlayWin-only stage.

Extract exclusively SHA-verified pure stdlib modules from existing independently
copied V91 archive. No live webroots, Zomorod source, factory, Django or DB.
"""
import ast,hashlib,io,json,os,tarfile,shutil
from pathlib import Path
ARCH=Path("/home/zomorod2/.v91_agents_safety_copy/v91-master-and-site-agents-20261018.tar.gz")
EXPECTED="4b825f80e06d632d5aac1717f82fac32b731ca89247a45b48f2222bdd86c858c"
PARENT=Path("/home/zomorod2/.private_mojplaywin_main_agents")
DEST=PARENT/"v91_missing_safe_policy_modules_20261018"
SOURCES=(
 "portal/autopilot_rules.py",
 "portal/commercial_quality.py",
 "portal/editorial_review_v26.py",
 "portal/venture_engine.py",
 "portal/workbook_generator.py",
 "portal/title_match.py",
 "portal/site_cycle_budget.py",
)
def require(cond,why):
 if not cond:raise RuntimeError(why)
def main():
 require(ARCH.is_file() and not ARCH.is_symlink(),"ORIGINAL_ARCHIVE_MISSING")
 require(PARENT.is_dir() and not PARENT.is_symlink() and PARENT.stat().st_mode&0o077==0,"PRIVATE_PARENT_REQUIRED")
 require(not DEST.exists() and not DEST.is_symlink(),"EXISTING_STAGE_NO_OVERWRITE")
 data=ARCH.read_bytes()
 require(hashlib.sha256(data).hexdigest()==EXPECTED,"SOURCE_ARCHIVE_HASH_MISMATCH")
 tmp=PARENT/".incoming_mpw_v91_pure_policies"
 require(not tmp.exists() and not tmp.is_symlink(),"INCOMING_COLLISION")
 tmp.mkdir(mode=0o700)
 try:
  (tmp/"portal").mkdir(mode=0o700)
  manifest={"tenant":"mojplaywin-main","source_sha256":EXPECTED,
            "source_code_preserved":True,"files":{},"auto_publish":False}
  (tmp/"portal"/"__init__.py").write_text("# Isolated V91 policy subset. No DB or factory.\n")
  os.chmod(tmp/"portal"/"__init__.py",0o600)
  with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as tar:
   indexed={x["path"]:x for x in json.load(tar.extractfile("V91_AGENT_MANIFEST.json"))["files"]}
   for relative in SOURCES:
    source="zomorodmelal/"+relative
    meta=indexed[source]
    item=tar.getmember(source)
    require(item.isfile() and item.size<40000,"BAD_SOURCE_TYPE")
    content=tar.extractfile(item).read()
    require(hashlib.sha256(content).hexdigest()==meta["sha256"],"V91_PER_FILE_HASH_INVALID")
    tree=ast.parse(content.decode("utf8"))
    forbidden={"django","subprocess","socket","requests"}
    imports=set()
    for node in ast.walk(tree):
     if isinstance(node,ast.Import):imports|={n.name.split(".")[0] for n in node.names}
     if isinstance(node,ast.ImportFrom) and node.level==0:imports.add((node.module or "").split(".")[0])
    require(not imports.intersection(forbidden),"DEPENDENT_MODULE_NOT_ALLOWED")
    destination=tmp/relative
    fd=os.open(str(destination),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"wb") as out:out.write(content)
    manifest["files"][relative]={"sha256":meta["sha256"],"bytes":len(content)}
  report=tmp/"manifest.json"
  report.write_text(json.dumps(manifest,sort_keys=True,indent=2),encoding="utf8")
  os.chmod(report,0o600)
  tmp.rename(DEST)
  print(json.dumps({"status":"MPW_SEVEN_MISSING_ORIGINAL_V91_RULE_ENGINES_STAGED",
   "verified_modules":len(SOURCES),"private_location":str(DEST),
   "live_sites_modified":False,"factory_modified":False,
   "original_source_modified":False,"no_payment_or_publication_enabled":True},sort_keys=True))
 except BaseException:
  if tmp.exists():shutil.rmtree(tmp,ignore_errors=True)
  raise
if __name__=="__main__":main()
