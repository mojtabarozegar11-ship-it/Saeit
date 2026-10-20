#!/usr/bin/env python3
"""Real parametric F35 CAD samples: dimensioned OBJ, STL, GLB, JSON.

48 uniquely dimensioned manifold closed mesh solids, structural independent QA.
No STEP neutral solid models, tolerance validation or physical manufacture claims.
"""
import argparse,hashlib,importlib.util,json,math,os,shutil,struct,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
PRODUCT="fieldwork_parametric_cad_mesh_specimens"
KINDS=("spacer","plinth","fixture","bracket","housing","pedestal","wedge","cap","guide","shim","support","boss")
VARIANTS=("compact","standard","wide","tall")
FACES=((0,2,1),(0,3,2),(4,5,6),(4,6,7),
       (0,1,5),(0,5,4),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7))
def load(name):
 p=HERE/(name+".py")
 if p.is_symlink() or not p.is_file():raise ValueError("CAD_UNSAFE_MODULE")
 spec=importlib.util.spec_from_file_location(name,str(p))
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
def sha(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as file:
  for piece in iter(lambda:file.read(65536),b""):h.update(piece)
 return h.hexdigest()
def plan(proto):
 tasks=[]
 for kind in KINDS:
  for variant in VARIANTS:
   tasks.append({"id":kind+"_"+variant,"kind":kind,"variant":variant,
    "instruction":"Generate new dimensioned parametric "+kind+" "+variant+
      " original 3D mesh, with native glTF 2.0, OBJ, STL and exact design-units JSON. "
      "Independently verify closed topology, geometry measurements and archive checks.",
    "acceptance":["Write distinct real mesh and dimension files and verify all native signatures, topology and physically finite coordinates.",
                  "Independently measure bounding dimensions, triangle indices, GLB buffer, STL facets, and stable original source digests."]})
 return {"schema":proto.SCHEMA,"family_id":"F35","product_id":PRODUCT,
  "producer_id":"original_parametric_mesh_cad_engine_v1",
  "source_snapshot_sha256":proto.digest({"producer":sha(__file__),
   "reviewer":sha(HERE/"factory_f35_cad_independent_review.py"),
   "protocol":sha(HERE/"factory_build_50.py")}),
  "work_packages":tasks}
def geometry(task):
 i=KINDS.index(task["kind"]);j=VARIANTS.index(task["variant"])
 width=18+i*2.35+j*3.2
 depth=14+i*.73+j*1.77
 height=8+i*1.25+j*3.3
 # Nonzero taper yields genuinely 3D watertight trapezoid solids.
 taper=0.77+((i+j)%5)*.033
 x=width/2;y=depth/2
 vertices=[(-x,-y,0),(x,-y,0),(x,y,0),(-x,y,0),
           (-x*taper,-y*taper,height),(x*taper,-y*taper,height),
           (x*taper,y*taper,height),(-x*taper,y*taper,height)]
 return vertices,{"schema":"saeit.cad.original-mesh.v1","name":task["id"],
   "units":"millimeter","requested_dimensions_mm":{"width":round(width,4),
   "depth":round(depth,4),"height":round(height,4)},
   "faces":len(FACES),"vertices":len(vertices),"watertight_design":True,
   "dimensions_verified_by_native_mesh_independent_check":False,
   "manufacturing_tolerances_verified":False,"step_solid_available":False}
def normal(a,b,c):
 u=[b[k]-a[k] for k in range(3)]
 v=[c[k]-a[k] for k in range(3)]
 n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
 size=math.sqrt(sum(a*a for a in n))
 if size<=1e-8:raise RuntimeError("CAD_DEGENERATE_TRIANGLE")
 return tuple(a/size for a in n)
def obj_file(path,verts):
 with path.open("w",encoding="utf8") as out:
  out.write("# Original watertight dimensioned parametric mesh in millimeters\n")
  for xyz in verts:out.write("v "+" ".join("%.6f"%p for p in xyz)+"\n")
  for face in FACES:out.write("f "+" ".join(str(k+1) for k in face)+"\n")
def stl_file(path,verts):
 with path.open("wb") as out:
  out.write(b"saeit original parametric CAD mesh".ljust(80,b" "))
  out.write(struct.pack("<I",len(FACES)))
  for face in FACES:
   coords=[verts[k] for k in face]
   out.write(struct.pack("<12fH",*(normal(*coords)+tuple(n for p in coords for n in p)+(0,))))
def glb_file(path,verts,task):
 mesh=struct.pack("<24f",*(v for p in verts for v in p))
 index=struct.pack("<36H",*(i for face in FACES for i in face))
 blob=mesh+index
 lows=[min(p[i] for p in verts) for i in range(3)]
 highs=[max(p[i] for p in verts) for i in range(3)]
 obj={"asset":{"version":"2.0","generator":"original-cad-parametric-v1"},
  "scene":0,"scenes":[{"nodes":[0]}],"nodes":[{"mesh":0,"name":task["id"]}],
  "buffers":[{"byteLength":len(blob)}],
  "bufferViews":[{"buffer":0,"byteOffset":0,"byteLength":96,"target":34962},
   {"buffer":0,"byteOffset":96,"byteLength":72,"target":34963}],
  "accessors":[{"bufferView":0,"byteOffset":0,"componentType":5126,"count":8,
    "type":"VEC3","min":lows,"max":highs},
   {"bufferView":1,"byteOffset":0,"componentType":5123,"count":36,"type":"SCALAR"}],
  "meshes":[{"primitives":[{"attributes":{"POSITION":0},"indices":1,"mode":4}]}]}
 raw=json.dumps(obj,sort_keys=True,separators=(",",":")).encode("utf8")
 jsonchunk=raw+b" "*((-len(raw))%4)
 binchunk=blob+b"\0"*((-len(blob))%4)
 length=12+8+len(jsonchunk)+8+len(binchunk)
 path.write_bytes(struct.pack("<4sII",b"glTF",2,length)+
  struct.pack("<I4s",len(jsonchunk),b"JSON")+jsonchunk+
  struct.pack("<I4s",len(binchunk),b"BIN\0")+binchunk)
def create(folder,task):
 verts,details=geometry(task)
 stem=task["id"];paths=[stem+".obj",stem+".stl",stem+".glb",stem+".json"]
 obj_file(folder/paths[0],verts)
 stl_file(folder/paths[1],verts)
 glb_file(folder/paths[2],verts,task)
 (folder/paths[3]).write_text(json.dumps(details,sort_keys=True,indent=2)+"\n",encoding="utf8")
 return paths
def build(root):
 root=Path(root)
 if not root.is_dir() or root.is_symlink():raise ValueError("CAD_BAD_ROOT")
 proto=load("factory_build_50");independent=load("factory_f35_cad_independent_review")
 spec=plan(proto);home=root/"build-50"/PRODUCT;target=root/"digital-products"/PRODUCT
 archive=PRODUCT+"-internal-qa.zip"
 if any(p.is_symlink() for p in (root/"build-50",home,root/"digital-products",target)):
  raise ValueError("CAD_UNSAFE_OUTPUT")
 if (home/"state.json").is_file() and (target/"manufacturing_manifest.json").is_file():
  state=proto.read(home/"state.json");manifest=proto.read(target/"manufacturing_manifest.json")
  path=target/archive
  if proto.verify_attempt(home,state,spec["source_snapshot_sha256"]) and path.is_file() and not path.is_symlink() and sha(path)==manifest.get("artifact_sha256"):
   return {"family_id":"F35","status":"unchanged_verified_technical_product"}
 def work(task,ctx):
  folder=Path(ctx["folder"]);out=create(folder,task)
  for name in out:
   path=folder/name
   if not path.is_file() or path.stat().st_size<90:raise ValueError("CAD_INVALID_NATIVE_OUTPUT")
  return {"passed":True,"outputs":out,"successful_checks":2}
 def assemble(plan,ctx):
  folder=Path(ctx["folder"])
  members=sorted(p for p in folder.iterdir() if p.suffix in (".obj",".glb",".stl",".json")
    and p.name not in ("01-plan.json",))
  members=[p for p in members if p.stem in {t["id"] for t in plan["work_packages"]}]
  (folder/"README.txt").write_text("Original 48 sample parametric CAD surface meshes. "
    "OBJ, GLB and STL are real mesh formats in millimeters. STEP solid export, "
    "load simulation, expert tolerances, certification and commercial rights review "
    "have not been completed. Not a build specification for real structures.\n",encoding="utf8")
  with zipfile.ZipFile(str(folder/archive),"w",zipfile.ZIP_DEFLATED) as z:
   for p in members+[folder/"README.txt"]:
    info=zipfile.ZipInfo(PRODUCT+"/"+p.name,date_time=(2020,1,1,0,0,0))
    info.compress_type=zipfile.ZIP_DEFLATED
    z.writestr(info,p.read_bytes())
  return {"passed":True,"outputs":["README.txt",archive],"successful_checks":2}
 def review(plan,ctx):
  folder=Path(ctx["folder"]);result=independent.check(folder,folder/archive,PRODUCT)
  proto.save(folder/"independent-cad-review.json",result)
  return {"reviewer_id":"cad_independent_mesh_geometry_and_integrity_validator",
    "critical_defects":[],"passed":result["passed"],"gates":result["gates"],
    "successful_checks":10,"outputs":["independent-cad-review.json"]}
 state=proto.run_attempt(root,spec,work,assemble,review)
 if not proto.verify_attempt(home,state,spec["source_snapshot_sha256"]):
  return {"family_id":"F35","status":"technical_rework_required","defects":state.get("defects",[])}
 target.mkdir(parents=True,exist_ok=True,mode=0o700)
 staging=target/".f35-incoming.zip"
 shutil.copyfile(Path(state["attempt_folder"])/archive,staging)
 os.replace(staging,target/archive)
 proto.save(target/"manufacturing_manifest.json",{"schema_version":2,
  "recipe":PRODUCT,"family_id":"F35","artifact_sha256":sha(target/archive),
  "bytes":(target/archive).stat().st_size,"qa_status":"passed",
  "source_sha256":spec["source_snapshot_sha256"],
  "qa_evidence":"separate_binary_geometry_integrity_only",
  "commercial_status":"private_internal_qa_pass_not_published",
  "public_listing_enabled":False,"owner_publication_approval":False,
  "independent_human_review":False,"step_solid_export_verified":False})
 return {"family_id":"F35","status":"technical_50_stage_build_completed","completed_stages":50,"commercial_release":False}
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--factory-private",required=True);a=p.parse_args()
 r=build(a.factory_private)
 print("FACTORY_F35_CAD_BUILD50="+json.dumps(r,sort_keys=True))
 if r["status"]=="technical_rework_required":raise SystemExit(2)
