#!/usr/bin/env python3
"""2000 ADDITIONAL callable offline utilities (40 x 50); 3000 including v1.
Operations share 75 stdlib implementations; no native manufacturing or commerce.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import difflib
import hashlib
from html import escape
from html.parser import HTMLParser
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import statistics
import sys
import unicodedata
from urllib.parse import urlencode, urlsplit, urlunsplit

spec=importlib.util.spec_from_file_location("factory_workbench_v1",str(Path(__file__).with_name("factory_1000_workbench.py")))
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
SCHEMA="saeit.factory.production-workbench.v2"
NAMES=(
 "Numeric sum","Numeric arithmetic mean","Numeric median","Population standard deviation",
 "Interpolated quantile","Cumulative sum","Moving average","Numeric min/max",
 "Positive-negative-zero counters","Numeric histogram",
 "Unicode case-fold","Unicode accent remover","Unique nonempty lines","Unified text diff",
 "Character histogram","Sorted unique words","Word bigram counter","Literal text replacement",
 "Line-end whitespace normalizer","Literal substring locator",
 "CSV group count","CSV group numeric sum","CSV distinct values","CSV top values","CSV missing-cell counts",
 "CSV column selector","CSV column renamer","CSV numeric type profiler","CSV bounded left join","CSV count pivot",
 "JSON pointer resolver","JSON stable list deduplicator","JSON type-shape profiler","Canonical JSON serializer",
 "Canonical JSON SHA-256","Recursive sensitive-key redactor","JSON record exact filter","JSON record sorter",
 "JSON record group counter","JSON Lines validator",
 "URL query encoder","File extension classifier","Safe Unicode artifact slugger","Escaped SVG tile generator",
 "HTML plain-text extractor","Markdown links parser","HTML-safe text escaper","ISO calendar timestamp normalizer",
 "Dependency topological sorter","Expected SHA-256 comparator"
)
assert len(NAMES)==50
TOOL_ID=re.compile(r"^F(?:0[1-9]|[1-3][0-9]|40)-T(?:0[1-9]|[1-6][0-9]|7[0-5])$")
SHA=re.compile(r"^[0-9a-f]{64}$")
def require(ok,why):
    base.require(ok,why)
def limited(s,label="text"):
    return base.as_text(s,label)
def number_vector(p):
    a=p.get("numbers")
    require(isinstance(a,list) and 1<=len(a)<=500,"NUMBERS_REQUIRED")
    require(all(type(x) in (int,float) and math.isfinite(x) and abs(x)<=1e12 for x in a),"NUMBER_INVALID")
    return [float(x) for x in a]
def csv_data(p):
    return base.rows_csv(p.get("csv",""))
def column(p,keys,name="column"):
    v=p.get(name,keys[0]);require(isinstance(v,str) and v in keys,"UNKNOWN_COLUMN");return v
def jsonrows(p):
    rows=p.get("rows")
    require(isinstance(rows,list) and len(rows)<=500 and all(isinstance(x,dict) for x in rows),"ROWS_INVALID")
    return rows
def stable(x):
    return base.json_bytes(x).decode("utf8")
def safe_key(v):
    require(isinstance(v,str) and 1<=len(v)<=80 and not v.startswith("__"),"KEY_INVALID")
    return v
def sample_field(p,name):
    return safe_key(p.get(name,"key"))
def base_score(p):
    keys,rows=csv_data(p);return keys,rows,column(p,keys)
class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.words=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):self.skip+=1
    def handle_endtag(self,tag):
        if tag in ("script","style") and self.skip:self.skip-=1
    def handle_data(self,data):
        if not self.skip:self.words.append(data)
def dispatch(op,p):
    base.dict_value(p,"payload")
    require(type(op) is int and 26<=op<=75,"UNKNOWN_OPERATION")
    if 26<=op<=35:
        n=number_vector(p)
        if op==26:return {"sum":math.fsum(n),"count":len(n)}
        if op==27:return {"mean":statistics.mean(n)}
        if op==28:return {"median":statistics.median(n)}
        if op==29:return {"pstdev":statistics.pstdev(n)}
        if op==30:
            q=p.get("quantile",0.5);require(type(q) in (float,int) and 0<=q<=1,"QUANTILE_INVALID")
            a=sorted(n);i=(len(a)-1)*q;lo=math.floor(i);return {"quantile":a[lo]+(a[math.ceil(i)]-a[lo])*(i-lo)}
        if op==31:return {"cumulative":[math.fsum(n[:i]) for i in range(1,len(n)+1)]}
        if op==32:
            window=p.get("window",2);require(type(window) is int and 1<=window<=len(n),"WINDOW_INVALID")
            return {"rolling_means":[statistics.mean(n[i-window:i]) for i in range(window,len(n)+1)]}
        if op==33:return {"min":min(n),"max":max(n),"range":max(n)-min(n)}
        if op==34:return {"positive":sum(v>0 for v in n),"negative":sum(v<0 for v in n),"zero":sum(v==0 for v in n)}
        bins=p.get("bins",5);require(type(bins) is int and 1<=bins<=50,"BINS_INVALID")
        lo=min(n);hi=max(n);counts=[0]*bins
        for v in n:counts[min(bins-1,int((v-lo)/(hi-lo)*bins) if hi>lo else 0)]+=1
        return {"min":lo,"max":hi,"bins":counts}
    if 36<=op<=45:
        t=limited(p.get("text",""))
        if op==36:return {"text":t.casefold()}
        if op==37:return {"text":"".join(c for c in unicodedata.normalize("NFKD",t) if not unicodedata.combining(c))}
        if op==38:return {"lines":list(dict.fromkeys(line.strip() for line in t.splitlines() if line.strip()))}
        if op==39:return {"unified_diff":"".join(difflib.unified_diff(t.splitlines(True),limited(p.get("after",""),"after").splitlines(True),fromfile="before",tofile="after"))}
        if op==40:return {"frequencies":dict(sorted(Counter(t).items(),key=lambda x:(-x[1],x[0]))[:100])}
        words=re.findall(r"\w+",t.casefold(),re.UNICODE)
        if op==41:return {"words":sorted(set(words))[:500]}
        if op==42:return {"bigrams":[{"pair":list(pair),"count":count} for pair,count in Counter(zip(words,words[1:])).most_common(50)]}
        if op==43:
            old=limited(p.get("find",""),"find");new=limited(p.get("replace",""),"replace")
            require(bool(old) and len(new)<=2000,"REPLACE_INVALID")
            return {"text":t.replace(old,new,1000)}
        if op==44:return {"text":"\n".join(line.rstrip() for line in t.splitlines())}
        needle=limited(p.get("find",""),"find");require(bool(needle),"FIND_EMPTY")
        return {"positions":[m.start() for m in re.finditer(re.escape(needle),t)][:1000]}
    if 46<=op<=55:
        keys,rows,k=base_score(p)
        if op==46:return {"groups":dict(sorted(Counter(row[k] for row in rows).items()))}
        if op==47:
            v=column(p,keys,"value_column");sums=defaultdict(list)
            for row in rows:
                try:value=float(row[v]);require(math.isfinite(value),"NONFINITE_CSV")
                except ValueError:raise ValueError("CSV_NONNUMERIC")
                sums[row[k]].append(value)
            return {"sums":{g:math.fsum(sums[g]) for g in sorted(sums)}}
        if op==48:return {"distinct":sorted(set(row[k] for row in rows))}
        if op==49:return {"ranked":[{"value":v,"count":c} for v,c in sorted(Counter(row[k] for row in rows).items(),key=lambda x:(-x[1],x[0]))[:50]]}
        if op==50:return {"empty":{field:sum(not row[field].strip() for row in rows) for field in keys}}
        if op==51:
            fields=p.get("fields",[k]);require(isinstance(fields,list) and 1<=len(fields)<=64 and len(set(fields))==len(fields) and all(f in keys for f in fields),"CSV_FIELDS_INVALID")
            return {"csv":base.csv_text(fields,[{f:r[f] for f in fields} for r in rows])}
        if op==52:
            new=safe_key(p.get("new_column","renamed"));require(new not in keys or new==k,"CSV_COLUMN_COLLISION")
            fields=[new if col==k else col for col in keys]
            return {"csv":base.csv_text(fields,[{new if key==k else key:v for key,v in row.items()} for row in rows])}
        if op==53:
            values=[r[k] for r in rows if r[k].strip()]
            def valid(v):
                try:return math.isfinite(float(v))
                except ValueError:return False
            return {"column":k,"inferred":"number" if values and all(valid(v) for v in values) else "text","nonempty":len(values)}
        if op==54:
            rkeys,right=base.rows_csv(p.get("right_csv",""));require(k in rkeys,"JOIN_KEY_MISSING")
            require(all(x not in keys for x in rkeys if x!=k),"JOIN_COLUMN_COLLISION")
            idx=defaultdict(list)
            for row in right:idx[row[k]].append(row)
            fields=keys+[x for x in rkeys if x!=k];out=[]
            for row in rows:
                for hit in idx.get(row[k],[{}]):
                    out.append(dict(row,**{f:hit.get(f,"") for f in rkeys if f!=k}))
                    require(len(out)<=1000,"JOIN_OUTPUT_LIMIT")
            return {"csv":base.csv_text(fields,out),"rows":len(out)}
        pivot=column(p,keys,"value_column");counts=Counter((r[k],r[pivot]) for r in rows)
        return {"cells":[{"row":a,"column":b,"count":count} for (a,b),count in sorted(counts.items())]}
    if 56<=op<=65:
        if op==56:
            obj=p.get("object");pointer=p.get("pointer","");require(isinstance(pointer,str) and len(pointer)<=500 and (pointer=="" or pointer.startswith("/")),"POINTER_INVALID")
            val=obj
            for raw in pointer.split("/")[1:] if pointer else []:
                key=raw.replace("~1","/").replace("~0","~")
                if isinstance(val,dict) and key in val:val=val[key]
                elif isinstance(val,list) and key.isdigit() and int(key)<len(val):val=val[int(key)]
                else:raise ValueError("POINTER_NOT_FOUND")
            return {"value":val}
        if op==57:
            a=p.get("items");require(isinstance(a,list) and len(a)<=500,"ITEMS_INVALID")
            seen=set();out=[]
            for item in a:
                h=stable(item)
                if h not in seen:seen.add(h);out.append(item)
            return {"items":out,"removed":len(a)-len(out)}
        if op==58:
            x=p.get("object")
            def shape(v,depth=0):
                require(depth<=7,"JSON_DEPTH_LIMIT")
                if isinstance(v,dict):return {k:shape(value,depth+1) for k,value in sorted(v.items())}
                if isinstance(v,list):return {"type":"array","count":len(v),"sample":shape(v[0],depth+1) if v else None}
                return "null" if v is None else type(v).__name__
            return {"shape":shape(x)}
        if op==59:return {"canonical_json":stable(p.get("object"))}
        if op==60:return {"sha256":hashlib.sha256(base.json_bytes(p.get("object"))).hexdigest()}
        if op==61:
            sensitive=p.get("sensitive_keys",["password","secret","token"]);require(isinstance(sensitive,list) and len(sensitive)<=30 and all(isinstance(k,str) for k in sensitive),"REDACTION_KEYS")
            names=set(k.casefold() for k in sensitive)
            def redact(v,depth=0):
                require(depth<=10,"REDACTION_DEPTH")
                if isinstance(v,dict):return {k:("***REDACTED***" if k.casefold() in names else redact(val,depth+1)) for k,val in v.items()}
                if isinstance(v,list):return [redact(x,depth+1) for x in v]
                return v
            return {"redacted":redact(p.get("object"))}
        if op in (62,63,64):
            rows=jsonrows(p);k=sample_field(p,"key")
            if op==62:return {"rows":[r for r in rows if r.get(k)==p.get("value")]}
            if op==63:return {"rows":sorted(rows,key=lambda r:stable(r.get(k)))}
            return {"groups":dict(sorted(Counter(stable(r.get(k)) for r in rows).items()))}
        t=limited(p.get("text",""))
        lines=[x for x in t.splitlines() if x.strip()];require(len(lines)<=500,"JSONL_ROWS_LIMIT")
        return {"rows":[json.loads(x) for x in lines],"count":len(lines)}
    if op==66:
        url=limited(p.get("url","https://example.invalid/path"),"url")
        parsed=urlsplit(url);require(parsed.scheme in ("https","http") and bool(parsed.netloc) and not parsed.username and not parsed.password,"URL_INVALID")
        query=p.get("params",{});require(isinstance(query,dict) and len(query)<=30 and all(isinstance(k,str) and type(v) in (str,int,float,bool) for k,v in query.items()),"PARAMETERS_INVALID")
        return {"url":urlunsplit((parsed.scheme,parsed.netloc,parsed.path,parsed.query+("&" if parsed.query and query else "")+urlencode(query),parsed.fragment))}
    if op==67:
        paths=p.get("paths",[]);require(isinstance(paths,list) and len(paths)<=200,"PATHS_INVALID")
        classes={".txt":"text",".md":"text",".csv":"data",".json":"data",".png":"image",".svg":"image",".pdf":"document",".mp4":"video",".wav":"audio",".html":"web",".py":"source"}
        return {"files":[{"path":base.safe_name(x),"type":classes.get(Path(x).suffix.lower(),"unknown")} for x in paths]}
    if op==68:
        t=limited(p.get("text",""),"text").casefold()
        slug=re.sub(r"[^\w\-]+","-",unicodedata.normalize("NFKC",t),flags=re.UNICODE).strip("-_")[:80]
        require(bool(slug),"EMPTY_SLUG");return {"slug":slug}
    if op==69:
        w=p.get("width",100);h=p.get("height",50);color=p.get("color","#16875a")
        require(type(w) is int and type(h) is int and 1<=w<=2048 and 1<=h<=2048,"SVG_DIMENSIONS")
        require(isinstance(color,str) and bool(re.fullmatch("#[0-9A-Fa-f]{6}",color)),"SVG_COLOR")
        label=limited(p.get("label","Verified tile"),"label")[:120]
        return {"svg":'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="'+escape(label,quote=True)+'" width="'+str(w)+'" height="'+str(h)+'"><rect width="100%" height="100%" fill="'+color+'"/></svg>'}
    if op==70:
        t=limited(p.get("text",""));parser=Extractor();parser.feed(t)
        return {"text":" ".join(" ".join(parser.words).split())}
    if op==71:
        t=limited(p.get("text",""))
        return {"links":[{"label":label,"destination":dest} for label,dest in re.findall(r"\[([^\]\n]{1,120})\]\(([^)\n]{1,500})\)",t)][:200]}
    if op==72:return {"html":escape(limited(p.get("text","")),quote=True)}
    if op==73:
        t=limited(p.get("date","2026-01-01T00:00:00+00:00"),"date");dt=datetime.fromisoformat(t.replace("Z","+00:00"))
        require(dt.tzinfo is not None,"TIMEZONE_REQUIRED")
        return {"utc":dt.astimezone(timezone.utc).isoformat(),"weekday":dt.strftime("%A")}
    if op==74:
        nodes=p.get("nodes");edges=p.get("edges",[])
        require(isinstance(nodes,list) and len(nodes)<=200 and all(isinstance(x,str) and 0<len(x)<=80 for x in nodes) and len(nodes)==len(set(nodes)),"NODES_INVALID")
        require(isinstance(edges,list) and len(edges)<=500 and all(isinstance(x,list) and len(x)==2 and x[0] in nodes and x[1] in nodes for x in edges),"EDGES_INVALID")
        adj=defaultdict(set);degree={x:0 for x in nodes}
        for a,b in edges:
            if b not in adj[a]:adj[a].add(b);degree[b]+=1
        order=[]
        while len(order)<len(nodes):
            ready=sorted(n for n in nodes if degree[n]==0 and n not in order)
            if not ready:raise ValueError("DEPENDENCY_CYCLE")
            for n in ready:
                order.append(n)
                for child in adj[n]:degree[child]-=1
        return {"order":order,"acyclic":True}
    entries=p.get("assets",[]);require(isinstance(entries,list) and len(entries)<=100,"ASSETS_INVALID")
    result=[]
    for item in entries:
        base.dict_value(item,"asset")
        expected=item.get("expected_sha256")
        require(isinstance(expected,str) and bool(SHA.fullmatch(expected)),"EXPECTED_HASH_REQUIRED")
        data=limited(item.get("text",""),"asset")
        result.append({"path":base.safe_name(item.get("path")),"matches":hashlib.sha256(data.encode("utf8")).hexdigest()==expected})
    return {"checks":result,"all_match":all(x["matches"] for x in result)}

def catalog(registry):
    old=base.catalog(registry)
    tools=list(old["tools"])
    for family in old["tools"][::25]:
        for ix,name in enumerate(NAMES,26):
            tools.append({"id":"%s-T%02d"%(family["family_id"],ix),
             "family_id":family["family_id"],"family_slug":family["family_slug"],"name":name,
             "operation":ix,"engine":"python_stdlib_offline_v2",
             "scope":"production_support_not_native_family_manufacturer",
             "readiness":"executable_verified_by_fixture_suite",
             "owner_release_approval":False,"commercial_publication_allowed":False})
    require(len(tools)==3000 and len({x["id"] for x in tools})==3000,"CATALOG_COUNT")
    return {"schema":SCHEMA,"families":40,"tools_count":3000,
     "new_bindings_added":2000,"existing_bindings_retained":1000,
     "shared_unique_operations":75,"native_manufacturing_executors_added":0,
     "commercially_approved_products_added":0,"tools":tools}
def invoke(cat,tool_id,payload):
    require(isinstance(tool_id,str) and bool(TOOL_ID.fullmatch(tool_id)),"TOOL_ID_INVALID")
    require(len(base.json_bytes(payload))<=base.MAX_INPUT,"PAYLOAD_TOO_LARGE")
    item=next((t for t in cat["tools"] if t["id"]==tool_id),None)
    require(item is not None,"TOOL_NOT_REGISTERED")
    if item["operation"]<=25:return base.invoke(cat,tool_id,payload)
    return {"tool_id":tool_id,"family_id":item["family_id"],"operation":item["name"],
       "result":dispatch(item["operation"],payload),"noncommercial":True}
def fixture(op):
    if op<=25:return base.fixture(op)
    p={"numbers":[1,2,3,4],"quantile":0.5,"window":2,"bins":2,
       "text":"one two two\nthree","after":"one changed\n","find":"two","replace":"three",
       "csv":"key,value\na,2\nb,4\na,3\n","column":"key","value_column":"value",
       "right_csv":"key,detail\na,yes\n","fields":["key"],"new_column":"group",
       "rows":[{"key":"a","n":2},{"key":"b","n":3}],"key":"key","value":"a",
       "object":{"a":{"b":2},"token":"secrete"},"pointer":"/a/b",
       "items":[{"a":1},{"a":1},{"a":2}],"sensitive_keys":["token"],
       "params":{"q":"hello world"},"paths":["docs/readme.md","assets/art.png"],
       "width":20,"height":20,"color":"#112233","label":"sample",
       "date":"2026-10-20T12:00:00+04:00",
       "nodes":["plan","build","test"],"edges":[["plan","build"],["build","test"]],
       "assets":[{"path":"a.txt","text":"abc","expected_sha256":hashlib.sha256(b"abc").hexdigest()}]}
    if op==65:p["text"]='{"x":1}\n{"y":2}'
    if op==68:p["text"]="Original Design"
    if op==70:p["text"]="<p>Working <b>example</b></p>"
    if op==71:p["text"]="[reference](https://example.org)"
    return p
def selftest(cat):
    checks={}
    for t in cat["tools"]:
        p=fixture(t["operation"]);a=invoke(cat,t["id"],p);b=invoke(cat,t["id"],p)
        require(a==b,"NONDETERMINISTIC_TOOL")
        checks[t["id"]]=hashlib.sha256(base.json_bytes(a)).hexdigest()
    require(len(checks)==3000,"SELFTEST_COUNT")
    return {"tested":3000,"passed":3000,"failed":0,"new_bindings":2000,
      "scope":"synthetic_fixtures_not_product_qa",
      "id_hash":hashlib.sha256(base.json_bytes(checks)).hexdigest()}
def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--registry",required=True);ap.add_argument("--catalog-out")
    ap.add_argument("--selftest",action="store_true");ap.add_argument("--tool-id")
    ap.add_argument("--workspace");ap.add_argument("--input-file");ap.add_argument("--output-file")
    args=ap.parse_args(argv)
    reg=Path(args.registry)
    require(reg.is_file() and not reg.is_symlink() and reg.stat().st_size<=2000000,"REGISTRY_INVALID")
    cat=catalog(json.loads(reg.read_text(encoding="utf8")))
    if args.catalog_out:
        dest=Path(args.catalog_out)
        require(dest.parent.is_dir() and not dest.parent.is_symlink() and not dest.is_symlink(),"CATALOG_DESTINATION_UNSAFE")
        base.atomic_bytes(dest,base.json_bytes(cat)+b"\n")
        print("FACTORY_3000_CATALOG="+str(cat["tools_count"]))
    if args.selftest:print("FACTORY_3000_QA="+json.dumps(selftest(cat),sort_keys=True))
    if args.tool_id:
        require(bool(args.workspace and args.input_file and args.output_file),"PRIVATE_IO_REQUIRED")
        src=base.scoped_path(args.workspace,args.input_file);dest=base.scoped_path(args.workspace,args.output_file)
        require(src!=dest and src.is_file() and not src.is_symlink() and src.stat().st_size<=base.MAX_INPUT,"INPUT_FILE_INVALID")
        data=invoke(cat,args.tool_id,json.loads(src.read_text(encoding="utf8")))
        base.atomic_bytes(dest,base.json_bytes(data)+b"\n")
        print("FACTORY_TOOL_EXECUTED="+args.tool_id)
    return 0
if __name__=="__main__":
    try:sys.exit(main())
    except (ValueError,RuntimeError,KeyError,TypeError) as exc:
        print(type(exc).__name__+":"+str(exc)[:240],file=sys.stderr);sys.exit(1)
