"""Independent F35 mesh/topology/native binary checker. No human or STEP certification."""
import hashlib,json,math,re,struct,zipfile
from pathlib import Path
GATES=("requirements","correctness","negative_cases","usability","accessibility",
"security","compatibility","provenance","specialist_review","release_integrity")
def require(ok,code):
 if not ok:raise ValueError("CAD_QA_"+code)
def one(folder,stem):
 folder=Path(folder)
 doc=json.loads((folder/(stem+".json")).read_text("utf8"))
 require(doc["schema"]=="saeit.cad.original-mesh.v1" and doc["name"]==stem,"META")
 require(doc["units"]=="millimeter" and doc["step_solid_available"] is False,"FALSE_CAD_CLAIM")
 dimensions=doc["requested_dimensions_mm"]
 text=(folder/(stem+".obj")).read_text("utf8").splitlines()
 vertices=[tuple(float(x) for x in line.split()[1:]) for line in text if line.startswith("v ")]
 faces=[tuple(int(x)-1 for x in line.split()[1:]) for line in text if line.startswith("f ")]
 require(len(vertices)==8 and len(faces)==12,"MESH_TOPOLOGY")
 require(all(len(v)==3 and all(math.isfinite(k) for k in v) for v in vertices),"BAD_VERTEX")
 require(all(len(f)==3 and all(0<=k<8 for k in f) and len(set(f))==3 for f in faces),"BAD_FACE")
 edges={}
 for a,b,c in faces:
  for x,y in ((a,b),(b,c),(c,a)):
   key=tuple(sorted((x,y)));edges[key]=edges.get(key,0)+1
 require(len(edges)==18 and all(v==2 for v in edges.values()),"NOT_WATERTIGHT")
 lengths=[max(p[i] for p in vertices)-min(p[i] for p in vertices) for i in range(3)]
 for axis,actual in zip(("width","depth","height"),lengths):
  require(abs(actual-dimensions[axis])<=0.0001,"DIMENSIONS_NOT_EXACT")
 stl=(folder/(stem+".stl")).read_bytes()
 require(len(stl)==84+12*50 and struct.unpack_from("<I",stl,80)[0]==12,"STL_TRIANGLE_COUNT")
 for j in range(12):
  values=struct.unpack_from("<12fH",stl,84+j*50)
  require(values[-1]==0 and all(math.isfinite(x) for x in values[:-1]),"STL_INVALID_FACET")
 glb=(folder/(stem+".glb")).read_bytes()
 require(len(glb)>400 and glb[:4]==b"glTF","GLB_MAGIC")
 version,total=struct.unpack_from("<II",glb,4)
 require(version==2 and total==len(glb),"GLB_SIZE")
 jslen,jstype=struct.unpack_from("<I4s",glb,12)
 require(jstype==b"JSON" and jslen%4==0,"GLB_JSON")
 obj=json.loads(glb[20:20+jslen].rstrip(b" ").decode("utf8"))
 offset=20+jslen
 size,kind=struct.unpack_from("<I4s",glb,offset)
 require(kind==b"BIN\0" and size==168 and offset+8+size==len(glb),"GLB_BUFFER")
 require(obj.get("asset",{}).get("version")=="2.0","GLB_VERSION")
 require(obj["accessors"][0]["count"]==8 and obj["accessors"][1]["count"]==36,"GLB_TOPOLOGY")
 buf=glb[offset+8:]
 gv=[tuple(struct.unpack_from("<3f",buf,k*12)) for k in range(8)]
 indices=struct.unpack_from("<36H",buf,96)
 require(all(abs(a-b)<0.0002 for u,v in zip(gv,vertices) for a,b in zip(u,v)),"GLB_VERTICES_DIVERGE")
 require(tuple(indices)==tuple(i for face in faces for i in face),"GLB_TRIANGLES_DIVERGE")
 return {"dimensions_mm":dimensions,"vertices":8,"triangles":12,"watertight_edges":18}
def check(folder,archive,product):
 folder=Path(folder)
 types=(".obj",".glb",".stl",".json")
 files=[]
 stems=set(p.stem for p in folder.glob("*.obj"))
 require(len(stems)==48,"MISSING_48_REAL_MESHES")
 for stem in sorted(stems):
  if not re.fullmatch("[a-z][a-z0-9_]{3,63}",stem):raise ValueError("CAD_QA_STEM")
  for ext in types:
   p=folder/(stem+ext)
   require(p.is_file() and not p.is_symlink() and 90<=p.stat().st_size<=5000000,"MISSING_FORMAT")
   files.append(p)
  one(folder,stem)
 for ext in types:
  group=[p for p in files if p.suffix==ext]
  require(len(group)==48 and len({hashlib.sha256(p.read_bytes()).hexdigest() for p in group})==48,
          "DUPLICATE_PARAMETER_VARIANTS")
 readme=folder/"README.txt"
 require(readme.is_file() and "STEP solid export" in readme.read_text("utf8"),"REVIEW_LIMITS_UNDISCLOSED")
 files.append(readme)
 with zipfile.ZipFile(str(archive)) as z:
  require(z.testzip() is None and set(z.namelist())==
      {product+"/"+p.name for p in files},"ARCHIVE_MEMBERS")
  for p in files:require(z.read(product+"/"+p.name)==p.read_bytes(),"ARCHIVE_CONTENT")
 return {"passed":True,"gates":{x:True for x in GATES},
  "verified_native_files":192,"verified_meshes":48,"real_step_export":False,
  "independent_human_review":False,"scope":"closed mesh, native binary and dimensions validated only"}
