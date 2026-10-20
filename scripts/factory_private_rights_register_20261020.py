#!/usr/bin/env python3
"""Record observable rights evidence on cPanel, not ownership or publication approval."""
import argparse,hashlib,importlib.util,json,os,re,sqlite3,tempfile
from pathlib import Path
SHA=re.compile(r"^[0-9a-f]{64}$")
KEYWORDS=("license","licence","copyright","permission","rights","attribution","author")
def dump(x):
 return (json.dumps(x,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode("utf8")
def hashbytes(b):return hashlib.sha256(b).hexdigest()
def load(p):
 if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=200000:raise ValueError("RIGHTS_UNTRUSTED_INPUT")
 v=json.loads(p.read_bytes())
 if not isinstance(v,dict):raise ValueError("RIGHTS_BAD_JSON")
 return v
def ensure_dir(p):
 if p.is_symlink():raise ValueError("RIGHTS_SYMLINK_DIRECTORY")
 p.mkdir(parents=True,exist_ok=True,mode=0o700)
 os.chmod(p,0o700)
def save(p,b):
 ensure_dir(p.parent)
 if p.is_symlink():raise ValueError("RIGHTS_SYMLINK_FILE")
 if p.exists():
  if p.read_bytes()!=b:raise ValueError("RIGHTS_IMMUTABLE_CONFLICT")
  return False
 fd,tmp=tempfile.mkstemp(prefix=".evidence-",dir=str(p.parent))
 try:
  with os.fdopen(fd,"wb") as fp:fp.write(b);fp.flush();os.fsync(fp.fileno())
  os.chmod(tmp,0o600);os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
 return True
def document(recipe,sha,manifest):
 members=manifest["files"]
 if len(members)!=97 or manifest["original_zip_sha256"]!=sha:
  raise ValueError("RIGHTS_SOURCE_INDEX_MISMATCH")
 assets=[]
 for item in members:
  name=item["name"];digest=item["sha256"];size=item["bytes"]
  if not name.startswith(recipe+"/") or not SHA.fullmatch(digest) or type(size)is not int or size<0:
   raise ValueError("RIGHTS_UNTRUSTED_ASSET")
  assets.append({"path":name,"sha256":digest,"bytes":size,
   "potential_rights_document_filename":any(t in name.rsplit("/",1)[-1].lower() for t in KEYWORDS),
   "creator_verified":False,"redistribution_permission_verified":False})
 return {"schema":"saeit.factory.cpanel-private-rights-register.v1","recipe":recipe,
   "original_archive_sha256":sha,"asset_count":len(assets),"assets":assets,
   "possible_rights_documents_are_not_grants":True,
   "proposed_claimant":"Zomorod Melal Agro-Industry Co. (LLC)",
   "claimant_chain_of_title_verified":False,"contracts_or_assignments_verified":False,
   "third_party_license_evidence_verified":False,"independent_legal_review_signed":False,
   "scientific_review_signed":False,"owner_publication_approval":False,
   "commercial_distribution_allowed":False,
   "status":"evidence_documented_legal_clearance_missing",
   "missing":["actual creator identities and authored source proof",
      "legally valid employment/commissioning/rights assignment records",
      "itemized third-party license grants and source links",
      "scope: reproduction, edits, commercial resale, sublicensing, territory, duration",
      "genuine specialist review and owner signature for this SHA"]}
def register(batch,verifier,dbpath,out):
 batch,verifier,dbpath,out=map(Path,(batch,verifier,dbpath,out))
 if batch.is_symlink() or not batch.is_dir() or not SHA.fullmatch(batch.name) or verifier.is_symlink() or not verifier.is_file():
  raise ValueError("RIGHTS_UNSAFE_BATCH")
 spec=importlib.util.spec_from_file_location("rights_private_verified_receiver",str(verifier))
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 verified=mod.verify(batch);receipt=load(batch/"verification.json")
 if receipt!=dict(verified,encrypted_transport_archive_sha256=batch.name) or verified["products_verified"]!=5 or verified["files_reconstructed"]!=485:
  raise ValueError("RIGHTS_TRANSFER_NOT_VERIFIED")
 if dbpath.is_symlink() or not dbpath.is_file() or out.is_symlink():raise ValueError("RIGHTS_UNSAFE_DB")
 with sqlite3.connect("file:"+str(dbpath)+"?mode=ro",uri=True) as db:
  found=db.execute("""SELECT COUNT(*) FROM factory_private_shard_candidates
    WHERE public_enabled=0 AND paid_price_irr IS NULL
      AND owner_approval='not_granted' AND rights_and_license_review='not_verified'""").fetchone()[0]
  if found<5:raise ValueError("RIGHTS_OFFICIAL_STORE_GATE_MISSING")
 ensure_dir(out);index=[];new=0
 for p in sorted(verified["products"],key=lambda x:x["recipe"]):
  recipe=p["recipe"];sha=p["original_sha256"]
  source=batch/"private-transport-shards"/recipe/sha/"receipt.json"
  doc=document(recipe,sha,load(source))
  contents=dump(doc);fingerprint=hashbytes(contents)
  target=out/sha
  ensure_dir(target)
  new+=int(save(target/(fingerprint+".rights.json"),contents))
  form=("UNSIGNED CHAIN-OF-TITLE REVIEW FORM\nProduct: "+recipe+"\nSHA256: "+sha+
   "\nContributors: [NOT VERIFIED]\nRights holder: [NOT VERIFIED]\n"+
   "Contracts/assignments: [NOT PROVIDED]\nThird-party grants: [NOT VERIFIED]\n"+
   "Reviewer signature: [MISSING]\nOwner publication signature: [MISSING]\n"+
   "This template grants no license and is not a sale permit.\n").encode("utf8")
  save(target/(fingerprint+".UNSIGNED.txt"),form)
  index.append({"recipe":recipe,"sha256":sha,"dossier_sha256":fingerprint,
   "asset_hashes_documented":97,"independent_license_clearance":False})
 summary={"schema":"saeit.factory.private-rights-summary.v1","batch_sha256":batch.name,
  "products":index,"asset_hashes_documented":485,
  "independent_legal_approvals":0,"owner_publication_approvals":0,"publications":0}
 save(out/"rights-summary.json",dump(summary))
 with sqlite3.connect(str(dbpath),timeout=15) as db:
  db.execute("""CREATE TABLE IF NOT EXISTS factory_private_rights_evidence(
   recipe TEXT NOT NULL, artifact_sha256 TEXT NOT NULL,dossier_sha256 TEXT NOT NULL,
   ownership_verified INTEGER NOT NULL DEFAULT 0 CHECK(ownership_verified=0),
   legal_clearance_verified INTEGER NOT NULL DEFAULT 0 CHECK(legal_clearance_verified=0),
   owner_release_signed INTEGER NOT NULL DEFAULT 0 CHECK(owner_release_signed=0),
   public_enabled INTEGER NOT NULL DEFAULT 0 CHECK(public_enabled=0),
   PRIMARY KEY(recipe,artifact_sha256))""")
  for p in index:
   before=db.execute("SELECT dossier_sha256 FROM factory_private_rights_evidence WHERE recipe=? AND artifact_sha256=?",(p["recipe"],p["sha256"])).fetchone()
   if before and before[0]!=p["dossier_sha256"]:raise ValueError("RIGHTS_REGISTER_CONFLICT")
   db.execute("INSERT OR IGNORE INTO factory_private_rights_evidence(recipe,artifact_sha256,dossier_sha256) VALUES(?,?,?)",
             (p["recipe"],p["sha256"],p["dossier_sha256"]))
  count=db.execute("SELECT COUNT(*),SUM(owner_release_signed),SUM(legal_clearance_verified) FROM factory_private_rights_evidence").fetchone()
  if count!=(5,0,0):raise ValueError("RIGHTS_REGISTER_GATE_MISMATCH")
  db.commit()
 return {"private_rights_dossiers":5,"new_dossiers":new,"asset_sha256_records":485,
         "signed_rights_grants":0,"owner_approvals":0,"sales":0,"publications":0}
if __name__=="__main__":
 p=argparse.ArgumentParser()
 for opt in ("batch","verifier","db","out"):p.add_argument("--"+opt,required=True)
 a=p.parse_args()
 print("CPANEL_PRIVATE_RIGHTS_REGISTER="+json.dumps(register(a.batch,a.verifier,a.db,a.out),sort_keys=True))
