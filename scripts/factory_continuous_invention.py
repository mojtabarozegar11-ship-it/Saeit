#!/usr/bin/env python3
"""Expandable offline *technical idea* supply for an independent VPS factory.

Produces only traceable engineering briefs for genuinely distinct calculations.
Never claims demand, science, copyright clearance, final QA or sale readiness.
No LLM/API/network, shell execution, fixed lifetime counter or unbounded tick.
Human-curated domain pattern packs can extend its knowledge without altering
the engine. An exhausted verified library reports exhaustion honestly.
"""
import ast
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile

SCHEMA = "saeit.factory.invention-pattern-pack.v1"
IDENT = re.compile(r"^[a-z][a-z0-9_]{2,60}$")
MAX_PACKS = 256
MAX_PATTERNS_PER_PACK = 128

# Audited user-input calculators. Each describes a distinct practical use case,
# never an invented market observation or unsupported scientific proposition.
BUILTIN = [
    ("transport_duration","Journey duration planner",
     "Calculate journey hours from measured distance and average travel speed.",
     "distance_km / speed_kmh","hours",
     [("distance_km","km"),("speed_kmh","km/hour")]),
    ("area_output","Measured field yield estimator",
     "Calculate nominal harvest mass from harvested area and measured yield.",
     "field_ha * yield_tonnes_per_ha","tonnes",
     [("field_ha","ha"),("yield_tonnes_per_ha","tonnes/ha")]),
    ("irrigation_run_time","Irrigation system runtime planner",
     "Calculate hours to deliver a stated measured water requirement at a constant measured flow.",
     "(area_ha * litres_per_ha) / flow_lph","hours",
     [("area_ha","ha"),("litres_per_ha","litres/ha"),("flow_lph","litres/hour")]),
    ("backup_storage","Raw backup replication requirement",
     "Compute raw backup bytes from object count, bytes per object and replica count.",
     "(object_count * bytes_per_object) * replicas","bytes",
     [("object_count","objects"),("bytes_per_object","bytes/object"),("replicas","dimensionless")]),
    ("technician_hours","Repair team theoretical duration",
     "Calculate theoretical minutes needed for counted defects and measured minutes per defect.",
     "(fault_count * minutes_per_fault) / technicians","minutes",
     [("fault_count","faults"),("minutes_per_fault","minutes/fault"),("technicians","workers")]),
    ("replenishment_window","Replenished stock coverage",
     "Calculate theoretical inventory coverage from current and incoming stock and daily usage.",
     "(current_stock + inbound_stock) / daily_demand","days",
     [("current_stock","units"),("inbound_stock","units"),("daily_demand","units/day")]),
    ("inspection_throughput","Valid inspection throughput",
     "Calculate accepted inspections per reviewer from reviewed and rejected records.",
     "(inspected - rejected) / reviewers","accepted/reviewer",
     [("inspected","inspections"),("rejected","inspections"),("reviewers","reviewers")]),
    ("budget_headroom","Budget headroom after allocation",
     "Calculate remaining nominal allocation after committed and operating expenses.",
     "(total_budget - committed) - operating","currency",
     [("total_budget","currency"),("committed","currency"),("operating","currency")]),
    ("transport_fuel","Fleet trip fuel planning",
     "Estimate litres needed for counted trips over a distance at observed fleet efficiency.",
     "(trips * distance_km) / km_per_litre","litres",
     [("trips","trips"),("distance_km","km/trip"),("km_per_litre","km/litre")]),
    ("lab_processing","Lab sample processing duration",
     "Calculate theoretical sample-processing time with parallel calibrated analysis stations.",
     "(samples * minutes_per_sample) / stations","minutes",
     [("samples","samples"),("minutes_per_sample","minutes/sample"),("stations","stations")]),
    ("solar_wh","Measured photovoltaic gross energy",
     "Estimate nominal energy from panel count, measured power and equivalent operating hours.",
     "(panel_count * watts_per_panel) * equivalent_hours","Wh",
     [("panel_count","panels"),("watts_per_panel","W/panel"),("equivalent_hours","hours")]),
    ("harvest_unit_cost","Harvest unit cost scenario",
     "Calculate direct unit cost using measured input and handling cost and accepted package count.",
     "(input_cost + handling_cost) / packages","currency/package",
     [("input_cost","currency"),("handling_cost","currency"),("packages","packages")]),
]
def _hash(data):
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf8")).hexdigest()

def _save(path,blob):
    if path.is_symlink() or path.parent.is_symlink():raise ValueError("INVENTION_UNSAFE_PATH")
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    data=blob if isinstance(blob,bytes) else (json.dumps(blob,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf8")
    fd,tmp=tempfile.mkstemp(dir=str(path.parent),prefix=".invention-")
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as writer:
            writer.write(data);writer.flush();os.fsync(writer.fileno())
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def _load_module(name):
    source=Path(__file__).with_name(name+".py")
    spec=importlib.util.spec_from_file_location(name+"_invention",source)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def patterns(root):
    all_patterns=list(BUILTIN)
    pack_root=root/"invention-pattern-packs"
    if pack_root.exists():
        if pack_root.is_symlink() or not pack_root.is_dir():
            raise ValueError("INVENTION_PACK_DIRECTORY_UNSAFE")
        files=sorted(pack_root.iterdir())
        if len(files)>MAX_PACKS:raise ValueError("INVENTION_PACK_LIMIT")
        for path in files:
            if path.is_symlink() or not path.is_file() or path.suffix!=".json" or path.stat().st_size>200000:
                raise ValueError("INVENTION_PACK_FILE_UNSAFE")
            doc=json.loads(path.read_text(encoding="utf8"))
            if doc.get("schema")!=SCHEMA or not isinstance(doc.get("patterns"),list) or len(doc["patterns"])>MAX_PATTERNS_PER_PACK:
                raise ValueError("INVENTION_PACK_SCHEMA_INVALID")
            for entry in doc["patterns"]:
                if not isinstance(entry,dict) or set(entry)!={"id","title","problem","expression","output_unit","inputs","family_id"}:
                    raise ValueError("INVENTION_PATTERN_SCHEMA_INVALID")
                if entry["family_id"] not in ("F27","F28"):
                    raise ValueError("INVENTION_ADAPTER_NOT_AVAILABLE")
                fields=entry["inputs"]
                if not isinstance(fields,list) or any(not isinstance(f,dict) or set(f)!={"name","unit"} for f in fields):
                    raise ValueError("INVENTION_PATTERN_FIELDS_INVALID")
                all_patterns.append((entry["id"],entry["title"],entry["problem"],entry["expression"],
                                    entry["output_unit"],[(f["name"],f["unit"]) for f in fields],entry["family_id"]))
    seen=set()
    for raw in all_patterns:
        code,title,problem,expr,out,fields=raw[:6]
        if (not isinstance(code,str) or not IDENT.fullmatch(code) or code in seen
                or not all(isinstance(x,str) for x in (title,problem,expr,out))
                or not 12<=len(title)<=120 or not 30<=len(problem)<=400
                or not 1<=len(fields)<=4 or len(expr)>160 or not out.strip()):
            raise ValueError("INVENTION_PATTERN_INVALID_OR_DUPLICATE")
        seen.add(code)
    return all_patterns

def _signature(expression,fields,unit,family):
    """Reject cosmetic title/variable renames with the same formula and units."""
    names=[x[0] for x in fields]
    tree=ast.parse(expression,mode="eval")
    class Normal(ast.NodeTransformer):
        def visit_Name(self,node):
            if node.id not in names:raise ValueError("INVENTION_FORMULA_BAD_VARIABLE")
            return ast.copy_location(ast.Name(id="v"+str(names.index(node.id)),ctx=ast.Load()),node)
    norm=Normal().visit(tree)
    return _hash({"expression":ast.dump(norm,include_attributes=False),
                  "units":[v for _,v in fields],"out":unit,"family":family})

def propose(root,*,max_new=1,max_pending=None):
    root=Path(root).expanduser().resolve()
    if root.is_symlink() or not root.is_dir():raise ValueError("INVENTION_ROOT_UNSAFE")
    # max_pending is accepted for callers from older releases, but is deliberately
    # ignored: a blocked downstream stage must never stop new work from entering.
    if type(max_new) is not int or not 1<=max_new<=5:
        raise ValueError("INVENTION_CAPACITY_INVALID")
    target=root/"engineering-briefs"
    if target.is_symlink():raise ValueError("INVENTION_BRIEF_DIR_UNSAFE")
    target.mkdir(parents=True,exist_ok=True,mode=0o700)
    statusdir=root/"invention-supply"
    if statusdir.is_symlink():raise ValueError("INVENTION_STATUS_DIR_UNSAFE")
    statusdir.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (statusdir/".lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        issued=[p for p in target.glob("auto_need_*.json") if p.is_file() and not p.is_symlink()]
        prior={p.stem for p in issued}
        completed=set()
        tickets=root/"engineering-intake"
        if tickets.is_dir() and not tickets.is_symlink():
            for receipt in tickets.glob("*.json"):
                if receipt.is_symlink():raise ValueError("INVENTION_UNSAFE_RECEIPT")
                if receipt.stat().st_size>200000:raise ValueError("INVENTION_RECEIPT_OVERSIZE")
                try:doc=json.loads(receipt.read_text("utf8"))
                except (ValueError,OSError):continue
                source=doc.get("source_id")
                if (doc.get("status")=="technical_prototype_built"
                        and isinstance(source,str) and source.startswith("auto_need_")):
                    completed.add(source)
        pending=len(prior-completed)
        builtins=patterns(root)
        novel=0;rejected=[];duplicates=0
        intake=_load_module("factory_design_intake")
        designer=_load_module("factory_recipe_designer")
        seen=set()
        for record in builtins:
            code,title,problem,expr,output,fields=record[:6]
            family=record[6] if len(record)>6 else "F28"
            sid="auto_need_"+code
            try:
                key=_signature(expr,fields,output,family)
            except (SyntaxError,ValueError) as error:
                rejected.append({"id":sid,"reason":type(error).__name__})
                continue
            if key in seen:
                duplicates+=1;continue
            seen.add(key)
            if sid in prior:continue
            if novel>=max_new:break
            definition={"title":title,"problem":problem,"expression":expr,
                        "inputs":[{"name":name,"unit":unit,"minimum":1,"maximum":100} for name,unit in fields],
                        "output_unit":output}
            brief={"schema":intake.SCHEMA,"family_id":family,
                   "mathematical_definition":definition}
            try:
                spec=intake.expand(brief,"factory_invention")
                names,training,holdout=designer.validate(spec)
                tree,searched=designer.synthesize(names,training)
                if not all(designer.close(designer.evaluate(tree,values),result)
                           for values,result in holdout):
                    raise ValueError("INVENTION_HOLDOUT_NOT_PASSED")
            except (ValueError,ArithmeticError) as error:
                rejected.append({"id":sid,"reason":str(error)[:120]})
                continue
            # Only an internally authored arithmetic brief. The evidence says
            # nothing about market demand, domain certification or rights to data.
            note=("INTERNAL MATHEMATICAL DESIGN REQUIREMENT ONLY\n"
                  "id="+sid+"\nengineering_sha256="+_hash(brief)+"\n"
                  "task="+problem+"\nformula="+expr+"\n"
                  "No evidence of customer demand, published research, or commercial license.\n")
            evidence=root/"invention-evidence"/(sid+".txt")
            _save(evidence,note.encode("utf8"))
            digest=hashlib.sha256(evidence.read_bytes()).hexdigest()
            proposal={"id":sid,"origin":"factory_invention","design_brief":brief,
                      "evidence":[{"path":str(evidence.relative_to(root)),"sha256":digest}],
                      "technical_scope":"measured_arithmetic_scenario_only",
                      "marketing_or_research_verified":False,
                      "commercial_release":False}
            _save(target/(sid+".json"),proposal)
            novel+=1;pending+=1
        report={"schema":"saeit.factory.continuous-invention-status.v1",
                "new_technical_briefs_this_tick":novel,
                "total_issued_briefs":len(prior)+novel,
                "pending_internal_design_briefs":pending,
                "known_design_patterns":len(builtins),
                "duplicate_pattern_skips":duplicates,
                "blocked_patterns":rejected[:15],
                "awaiting_additional_verified_needs":novel==0 and pending==0,
                "store_ready_products":0,"commercial_release":False}
        _save(statusdir/"status.json",report)
        return report

if __name__=="__main__":
    import argparse
    a=argparse.ArgumentParser()
    a.add_argument("--factory-private",required=True)
    a.add_argument("--max-new",type=int,default=1)
    v=a.parse_args()
    print("FACTORY_INVENTION_SUPPLY="+json.dumps(propose(v.factory_private,max_new=v.max_new),sort_keys=True))
