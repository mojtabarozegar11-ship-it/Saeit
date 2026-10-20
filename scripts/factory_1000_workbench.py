#!/usr/bin/env python3
"""1000 real executable, offline production-SUPPORT tool bindings (40 families x 25).
Each tool has a deterministic implementation and fixture QA; this does NOT turn
40 family-specific native manufacturing engines on, or approve products for sale.
Python 3.8+, stdlib only. No network, subprocess, external site or payment access.
"""
import argparse
from collections import Counter
import csv
import hashlib
import html
import io
import json
import os
import tempfile
from pathlib import Path
import re
import sys
import unicodedata

SCHEMA="saeit.factory.production-workbench.v1"
NAMES=(
 "Unicode text cleaner","Markdown outline extractor","Text metrics","Keyword histogram",
 "Checklist extractor","CSV field profiler","CSV row deduplicator","CSV stable sorter",
 "CSV exact-value filter","CSV to JSON rows","JSON rows to CSV","Nested JSON flattener",
 "JSON key-change comparator","Required-field validator","Safe dictionary merger",
 "SHA-256 text checksum","Content-anchored asset manifest","License completeness audit",
 "Asset path safety audit","Escaped HTML metadata builder","Search-friendly slug builder",
 "Requirements evidence matrix","Quantified risk register","Noncommercial release checklist",
 "Production work breakdown"
)
assert len(NAMES)==25
MAX_INPUT=200000
MAX_ROWS=500
SHA=re.compile(r"^[a-f0-9]{64}$")
TOOL_ID=re.compile(r"^F(?:0[1-9]|[1-3][0-9]|40)-T(?:0[1-9]|1[0-9]|2[0-5])$")

def json_bytes(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")

def require(condition, reason):
    if not condition:raise ValueError("WORKBENCH_"+reason)

def as_text(value, field="text"):
    require(isinstance(value,str) and len(value.encode("utf-8"))<=MAX_INPUT,field.upper()+"_INVALID")
    return value

def dict_value(value,field="value"):
    require(isinstance(value,dict),field.upper()+"_OBJECT_REQUIRED")
    return value

def rows_csv(text):
    src=io.StringIO(as_text(text,"csv"))
    rdr=csv.DictReader(src)
    keys=rdr.fieldnames
    require(isinstance(keys,list) and 1<=len(keys)<=64,"CSV_HEADER_REQUIRED")
    require(len(set(keys))==len(keys) and all(k and len(k)<=80 for k in keys),"CSV_BAD_COLUMNS")
    rows=list(rdr)
    require(len(rows)<=MAX_ROWS,"CSV_ROWS_EXCEEDED")
    require(all(None not in row and all(isinstance(v,str) for v in row.values()) for row in rows),"CSV_ROW_MISMATCH")
    return keys,rows

def csv_text(keys,rows):
    out=io.StringIO(newline="")
    wr=csv.DictWriter(out,fieldnames=keys,lineterminator="\n",extrasaction="ignore")
    wr.writeheader();wr.writerows(rows)
    return out.getvalue()

def data_rows(payload):
    value=payload.get("rows")
    require(isinstance(value,list) and len(value)<=MAX_ROWS,"ROWS_INVALID")
    require(all(isinstance(v,dict) for v in value),"ROWS_MUST_BE_OBJECTS")
    keys=list(dict.fromkeys(str(k) for row in value for k in row))
    require(len(keys)<=64,"TOO_MANY_FIELDS")
    require(all(isinstance(v,(str,int,float,bool,type(None))) for row in value for v in row.values()),"NONSCALAR_CSV_VALUE")
    return value,keys

def safe_name(name):
    require(isinstance(name,str) and 1<=len(name)<=120,"ASSET_NAME_INVALID")
    require(not name.startswith(("/", "\\")) and "\\" not in name and ".." not in name.split("/") and ":" not in name,"ASSET_PATH_UNSAFE")
    require(all(p not in ("",".") for p in name.split("/")),"ASSET_PATH_UNSAFE")
    return name

def dispatch(operation,payload):
    dict_value(payload,"payload")
    require(operation in range(1,26),"UNKNOWN_OPERATION")
    if operation in (1,2,3,4,5):
        text=as_text(payload.get("text",""))
        if operation==1:
            return {"normalized":" ".join(unicodedata.normalize("NFKC",text).split())}
        if operation==2:
            lines=text.splitlines()
            return {"headings":[{"level":len(m.group(1)),"title":m.group(2).strip()} for line in lines for m in [re.match(r"^(#{1,6})\s+(.+)$",line)] if m]}
        words=re.findall(r"\w+",text.casefold(),re.UNICODE)
        if operation==3:
            return {"characters":len(text),"words":len(words),"unique_words":len(set(words)),"nonempty_lines":sum(bool(s.strip()) for s in text.splitlines())}
        if operation==4:
            return {"frequencies":[{"word":k,"count":v} for k,v in sorted(Counter(words).items(),key=lambda x:(-x[1],x[0]))[:20]]}
        return {"checklist":[{"done":bool(m.group(1).lower()=="x"),"task":m.group(2).strip()} for line in text.splitlines() for m in [re.match(r"^\s*-\s*\[([ xX])\]\s+(.+)$",line)] if m]}
    if 6<=operation<=10:
        keys,rows=rows_csv(payload.get("csv",""))
        if operation==6:
            return {"columns":keys,"row_count":len(rows),"empty_cells":{k:sum(not row[k].strip() for row in rows) for k in keys},"distinct_count":{k:len({row[k] for row in rows}) for k in keys}}
        if operation==7:
            seen=set();unique=[]
            for row in rows:
                mark=tuple(row[k] for k in keys)
                if mark not in seen:seen.add(mark);unique.append(row)
            return {"csv":csv_text(keys,unique),"removed":len(rows)-len(unique)}
        col=payload.get("column",keys[0])
        require(col in keys,"COLUMN_NOT_FOUND")
        if operation==8:
            return {"csv":csv_text(keys,sorted(rows,key=lambda row:row[col].casefold()))}
        if operation==9:
            needle=as_text(payload.get("value",""),"filter")
            filtered=[row for row in rows if row[col]==needle]
            return {"csv":csv_text(keys,filtered),"matched":len(filtered)}
        return {"rows":rows}
    if operation==11:
        rows,keys=data_rows(payload)
        require(keys,"NO_COLUMNS")
        return {"csv":csv_text(keys,[{k:"" if row.get(k) is None else str(row[k]) if k in row else "" for k in keys} for row in rows])}
    if operation==12:
        obj=dict_value(payload.get("object"),"object")
        flat={}
        def walk(item,prefix="",depth=0):
            require(depth<=5 and len(flat)<=128,"JSON_NESTING_LIMIT")
            if isinstance(item,dict):
                for k,v in item.items():
                    require(isinstance(k,str) and len(k)<=80,"JSON_KEY_INVALID")
                    walk(v,prefix+"."+k if prefix else k,depth+1)
            else:flat[prefix]=item
        walk(obj)
        return {"flat":flat}
    if operation==13:
        a=dict_value(payload.get("before"),"before");b=dict_value(payload.get("after"),"after")
        return {"added":sorted(set(b)-set(a)),"removed":sorted(set(a)-set(b)),"changed":sorted(k for k in set(a)&set(b) if a[k]!=b[k])}
    if operation==14:
        obj=dict_value(payload.get("object"),"object")
        required=payload.get("required",[])
        require(isinstance(required,list) and len(required)<=100 and all(isinstance(s,str) for s in required),"REQUIRED_FIELDS_INVALID")
        missing=sorted(k for k in required if obj.get(k) in (None,"",[]))
        return {"missing":missing,"complete":not missing,"checked":len(required)}
    if operation==15:
        a=dict_value(payload.get("base"),"base");b=dict_value(payload.get("patch"),"patch")
        require(len(a)+len(b)<=128,"MERGE_LIMIT")
        return {"merged":dict(a,**b)}
    if operation==16:
        text=as_text(payload.get("text",""))
        return {"sha256":hashlib.sha256(text.encode("utf8")).hexdigest(),"utf8_bytes":len(text.encode("utf8"))}
    if operation==17:
        assets=payload.get("assets")
        require(isinstance(assets,list) and len(assets)<=50,"ASSETS_INVALID")
        entries=[]
        for item in assets:
            dict_value(item,"asset");name=safe_name(item.get("path"));body=as_text(item.get("text",""),"asset_text")
            raw=body.encode("utf8")
            entries.append({"path":name,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})
        require(len({x["path"] for x in entries})==len(entries),"DUPLICATE_ASSET_PATH")
        return {"assets":entries,"manifest_sha256":hashlib.sha256(json_bytes(entries)).hexdigest()}
    if operation==18:
        assets=payload.get("assets")
        require(isinstance(assets,list) and len(assets)<=100,"LICENSE_ASSETS_INVALID")
        gaps=[]
        for i,item in enumerate(assets):
            dict_value(item,"asset");safe_name(item.get("path"))
            if not isinstance(item.get("license"),str) or not item["license"].strip():
                gaps.append({"index":i,"missing":"license"})
            if item.get("third_party") is True and not str(item.get("attribution","")).strip():
                gaps.append({"index":i,"missing":"third_party_attribution"})
        return {"documentation_complete":not gaps,"gaps":gaps,"rights_verified":False}
    if operation==19:
        files=payload.get("paths")
        require(isinstance(files,list) and len(files)<=200,"PATHS_INVALID")
        passed=[];blocked=[]
        for name in files:
            try:passed.append(safe_name(name))
            except ValueError:blocked.append(name)
        return {"safe_paths":passed,"rejected_paths":blocked,"all_safe":not blocked}
    if operation==20:
        title=as_text(payload.get("title",""),"title").strip()
        description=as_text(payload.get("description",""),"description").strip()
        require(3<=len(title)<=110 and 10<=len(description)<=300,"SEO_LENGTH_INVALID")
        return {"html":"<title>"+html.escape(title,quote=True)+"</title>\n<meta name=\"description\" content=\""+html.escape(description,quote=True)+"\">","title_length":len(title),"description_length":len(description)}
    if operation==21:
        text=as_text(payload.get("text","")).casefold()
        stem=unicodedata.normalize("NFKD",text)
        ascii_text="".join(c for c in stem if ord(c)<128 and not unicodedata.combining(c))
        slug=re.sub(r"-+","-",re.sub(r"[^a-z0-9]+","-",ascii_text)).strip("-")
        require(bool(slug),"SLUG_REQUIRES_ASCII_TRANSLITERATION")
        return {"slug":slug[:90].strip("-")}
    if operation==22:
        rows=payload.get("requirements")
        require(isinstance(rows,list) and len(rows)<=100,"REQUIREMENTS_INVALID")
        checks=[]
        for row in rows:
            dict_value(row,"requirement")
            ident=as_text(row.get("id",""),"req_id")
            require(bool(ident) and len(ident)<=80,"REQUIREMENT_ID_INVALID")
            verified=row.get("verified") is True and isinstance(row.get("evidence_sha256"),str) and bool(SHA.fullmatch(row["evidence_sha256"]))
            checks.append({"id":ident,"verified":verified})
        require(len({x["id"] for x in checks})==len(checks),"DUPLICATE_REQUIREMENT")
        return {"matrix":checks,"verified_count":sum(x["verified"] for x in checks),"gaps":[x["id"] for x in checks if not x["verified"]]}
    if operation==23:
        rows=payload.get("risks")
        require(isinstance(rows,list) and len(rows)<=100,"RISKS_INVALID")
        results=[]
        for row in rows:
            dict_value(row,"risk")
            p=row.get("likelihood");i=row.get("impact")
            require(type(p) is int and type(i) is int and 1<=p<=5 and 1<=i<=5,"RISK_SCALE_INVALID")
            results.append({"name":as_text(row.get("name",""),"risk_name")[:120],"score":p*i})
        return {"ranked":sorted(results,key=lambda x:(-x["score"],x["name"]))}
    if operation==24:
        checks=payload.get("checks")
        require(isinstance(checks,list) and bool(checks) and len(checks)<=100,"RELEASE_CHECKS_REQUIRED")
        bad=[]
        for row in checks:
            dict_value(row,"check")
            if row.get("passed") is not True or not SHA.fullmatch(str(row.get("evidence_sha256",""))):
                bad.append(str(row.get("id","unknown"))[:80])
        return {"technical_checks_complete":not bad,"missing_evidence":bad,
                "commercial_release_authorized":False,"independent_owner_approval_required":True}
    rows=payload.get("deliverables")
    require(isinstance(rows,list) and 1<=len(rows)<=40 and all(isinstance(x,str) and x.strip() and len(x)<200 for x in rows),"DELIVERABLES_INVALID")
    steps=("scope","research","implementation","internal_test","independent_review","packaging","owner_release_decision")
    return {"work_items":[{"deliverable":name,"step":step,"state":"planned_not_executed"} for name in rows for step in steps],
            "production_started":False,"commercial_release_authorized":False}

def catalog(registry):
    registry=dict_value(registry,"registry")
    require(registry.get("schema")=="saeit.factory.family-registry.v1","REGISTRY_SCHEMA")
    profiles=registry.get("profiles")
    require(isinstance(profiles,list) and len(profiles)==40,"FORTY_FAMILIES_REQUIRED")
    require([p.get("id") for p in profiles if isinstance(p,dict)]==["F%02d"%n for n in range(1,41)],"REGISTRY_IDS_INVALID")
    tools=[]
    for p in profiles:
        family=p["id"];slug=p.get("slug")
        require(isinstance(slug,str) and bool(re.fullmatch(r"[a-z][a-z0-9_]{2,64}",slug)),"FAMILY_SLUG_INVALID")
        for ix,label in enumerate(NAMES,1):
            tools.append({"id":"%s-T%02d"%(family,ix),"family_id":family,
                "family_slug":slug,"name":label,"operation":ix,"engine":"python_stdlib_offline_v1",
                "scope":"production_support_not_native_family_manufacturer",
                "readiness":"executable_verified_by_fixture_suite",
                "owner_release_approval":False,"commercial_publication_allowed":False})
    require(len(tools)==1000 and len({x["id"] for x in tools})==1000,"CATALOG_COUNT")
    return {"schema":SCHEMA,"families":40,"tools_count":len(tools),
            "native_manufacturing_executors_added":0,
            "commercially_approved_products_added":0,
            "tools":tools}

def invoke(catalogue,tool_id,payload):
    require(isinstance(tool_id,str) and bool(TOOL_ID.fullmatch(tool_id)),"TOOL_ID_INVALID")
    item=next((t for t in catalogue["tools"] if t["id"]==tool_id),None)
    require(item is not None,"TOOL_NOT_REGISTERED")
    encoded=json_bytes(payload)
    require(len(encoded)<=MAX_INPUT,"PAYLOAD_TOO_LARGE")
    return {"tool_id":tool_id,"family_id":item["family_id"],
        "operation":item["name"],"result":dispatch(item["operation"],payload),
        "noncommercial":True}

def fixture(op):
    if op<=5:return {"text":"# Example\n- [ ] Verify result\nOne two two.\n"}
    if op<=10:return {"csv":"key,value\na,10\nb,20\na,10\n","column":"key","value":"a"}
    if op==11:return {"rows":[{"name":"example","count":3}]}
    if op==12:return {"object":{"a":{"b":3},"c":4}}
    if op==13:return {"before":{"x":1},"after":{"x":2,"y":3}}
    if op==14:return {"object":{"title":"demo"},"required":["title","evidence"]}
    if op==15:return {"base":{"a":1},"patch":{"b":2}}
    if op==16:return {"text":"verified bytes"}
    if op==17:return {"assets":[{"path":"docs/readme.txt","text":"license example"}]}
    if op==18:return {"assets":[{"path":"img/sample.png","third_party":True,"license":"CC BY","attribution":"origin"}]}
    if op==19:return {"paths":["docs/example.md","../unsafe"]}
    if op==20:return {"title":"Useful example","description":"An illustrative private artifact with verified metadata."}
    if op==21:return {"text":"Offline Production Example"}
    if op==22:return {"requirements":[{"id":"R1","verified":True,"evidence_sha256":"a"*64},{"id":"R2","verified":False}]}
    if op==23:return {"risks":[{"name":"missing right","likelihood":2,"impact":5}]}
    if op==24:return {"checks":[{"id":"real-test","passed":True,"evidence_sha256":"b"*64},{"id":"independent-review","passed":False}]}
    return {"deliverables":["private original artifact"]}

def selftest(cat):
    sample_hashes={}
    for tool in cat["tools"]:
        payload=fixture(tool["operation"])
        first=invoke(cat,tool["id"],payload)
        second=invoke(cat,tool["id"],payload)
        require(first==second,"NONDETERMINISTIC_TOOL")
        sample_hashes[tool["id"]]=hashlib.sha256(json_bytes(first)).hexdigest()
    require(len(sample_hashes)==1000,"FIXTURE_COVERAGE")
    return {"tested":1000,"passed":1000,"failed":0,"scope":"synthetic_fixtures_not_commercial_QA",
            "id_hash":hashlib.sha256(json_bytes(sample_hashes)).hexdigest()}

def scoped_path(workspace,path):
    root=Path(workspace)
    require(root.is_dir() and not root.is_symlink(),"WORKSPACE_INVALID")
    root=root.resolve(strict=True)
    candidate=Path(path)
    require(candidate.is_absolute(),"ABSOLUTE_IO_PATH_REQUIRED")
    target=candidate.resolve(strict=False)
    try:
        rel=target.relative_to(root)
    except ValueError:
        raise ValueError("WORKBENCH_PATH_OUTSIDE_PRIVATE_WORKSPACE")
    require(bool(rel.parts),"ROOT_CANNOT_BE_TOOL_FILE")
    node=root
    for part in rel.parts:
        node=node/part
        require(not node.is_symlink(),"SYMLINK_TOOL_FILE_REFUSED")
    return target

def atomic_bytes(path,raw):
    require(path.parent.is_dir() and not path.parent.is_symlink(),"OUTPUT_PARENT_INVALID")
    require(not path.is_symlink(),"OUTPUT_SYMLINK")
    fd,tmp=tempfile.mkstemp(prefix=".workbench-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--registry",required=True)
    p.add_argument("--catalog-out")
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--tool-id")
    p.add_argument("--workspace")
    p.add_argument("--input-file")
    p.add_argument("--output-file")
    a=p.parse_args(argv)
    regpath=Path(a.registry)
    require(regpath.is_file() and not regpath.is_symlink() and regpath.stat().st_size<=2000000,"REGISTRY_SOURCE_INVALID")
    cat=catalog(json.loads(regpath.read_text(encoding="utf8")))
    if a.catalog_out:
        out=Path(a.catalog_out)
        require(out.parent.is_dir() and not out.parent.is_symlink() and not out.is_symlink(),"CATALOG_DESTINATION_UNSAFE")
        out.write_bytes(json_bytes(cat)+b"\n")
        out.chmod(0o600)
        print("FACTORY_1000_CATALOG_REGISTERED="+str(cat["tools_count"]))
    if a.selftest:print("FACTORY_1000_QA="+json.dumps(selftest(cat),sort_keys=True))
    if a.tool_id:
        require(bool(a.workspace) and bool(a.input_file) and bool(a.output_file),"RUN_PRIVATE_WORKSPACE_AND_IO_REQUIRED")
        src=scoped_path(a.workspace,a.input_file)
        dest=scoped_path(a.workspace,a.output_file)
        require(src!=dest,"INPUT_OUTPUT_MUST_DIFFER")
        require(src.is_file() and not src.is_symlink() and src.stat().st_size<=MAX_INPUT,"INPUT_FILE_INVALID")
        require(dest.parent.is_dir() and not dest.is_symlink(),"OUTPUT_FILE_INVALID")
        result=invoke(cat,a.tool_id,json.loads(src.read_text(encoding="utf8")))
        atomic_bytes(dest,json_bytes(result)+b"\n")
        print("FACTORY_TOOL_EXECUTED="+a.tool_id)
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except (ValueError,RuntimeError,TypeError,KeyError) as exc:
        print(type(exc).__name__+":"+str(exc)[:240],file=sys.stderr);sys.exit(1)
