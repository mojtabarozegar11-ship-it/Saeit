#!/usr/bin/env python3
"""Ten genuine, additive private generations for authenticated F27/F28 products.

Each generation adds an executable customer function and its acceptance test.
No original source, existing ZIP, website, financial state or signature is edited.
Unsupported families remain blocked. Ten technical builds != 1000/1000 approval.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

SCHEMA="saeit.factory.ten-real-generations.v1"
RECIPE=re.compile(r"^(?:sheet|synth)_[0-9a-f]{24}$")
REVISIONS={
    "verified-summary-v3": "# STATS_API_V3_START",
    "verified-distribution-v4": "# DISTRIBUTION_API_V4_START",
    "verified-grouped-statistics-v5": "# GROUPED_STATISTICS_API_V5_START",
}
HEADER='''"""Versioned offline features for a validated factory arithmetic tool."""
from calculator import NAMES, calculate, calculate_batch
from decimal import Decimal, localcontext
import csv
import html
import io
import json

'''
TEST_HEADER='''import csv
from decimal import Decimal, localcontext
import io
import json
from pathlib import Path
import unittest
from calculator import NAMES, calculate
from generation_features import *
SPEC=json.loads((Path(__file__).parent/"design_request.json").read_text(encoding="utf8"))
ROWS=[row["inputs"] for row in SPEC["training_examples"][:2]]
VALUES=[Decimal(calculate(row)["result"]) for row in ROWS]
class RealFeatureAcceptanceTests(unittest.TestCase):
'''
FEATURES=[
("validated_batch_metadata",
'''def input_report(rows):
    batch=calculate_batch(rows)
    return {"count":batch["count"],"fields":list(NAMES)}

''',
'''    def test_g01_batch_metadata(self):
        self.assertEqual(input_report(ROWS),{"count":2,"fields":list(NAMES)})
        with self.assertRaises(ValueError):input_report([{}])

'''),
("downloadable_csv",
'''def csv_export(rows):
    batch=calculate_batch(rows)
    out=io.StringIO()
    writer=csv.writer(out,lineterminator="\\n")
    writer.writerow([*NAMES,"result","unit"])
    for inputs,answer in zip(rows,batch["results"]):
        writer.writerow([*(str(inputs[name]) for name in NAMES),answer["result"],answer["unit"]])
    return out.getvalue()

''',
'''    def test_g02_csv_export(self):
        table=list(csv.reader(io.StringIO(csv_export(ROWS))))
        self.assertEqual(table[0],[*NAMES,"result","unit"])
        self.assertEqual([Decimal(row[-2]) for row in table[1:]],VALUES)
        with self.assertRaises(ValueError):csv_export([{}])

'''),
("downloadable_tsv",
'''def tsv_export(rows):
    batch=calculate_batch(rows)
    out=io.StringIO()
    writer=csv.writer(out,delimiter="\\t",lineterminator="\\n")
    writer.writerow([*NAMES,"result","unit"])
    for inputs,answer in zip(rows,batch["results"]):
        writer.writerow([*(str(inputs[name]) for name in NAMES),answer["result"],answer["unit"]])
    return out.getvalue()

''',
'''    def test_g03_tsv_export(self):
        table=list(csv.reader(io.StringIO(tsv_export(ROWS)),delimiter="\\t"))
        self.assertEqual(table[0],[*NAMES,"result","unit"])
        self.assertEqual([Decimal(row[-2]) for row in table[1:]],VALUES)

'''),
("streaming_json_lines",
'''def jsonl_export(rows):
    batch=calculate_batch(rows)
    return "".join(json.dumps({"inputs":inputs,"output":output},sort_keys=True)+"\\n"
                   for inputs,output in zip(rows,batch["results"]))

''',
'''    def test_g04_jsonl_export(self):
        lines=[json.loads(row) for row in jsonl_export(ROWS).splitlines()]
        self.assertEqual(len(lines),2)
        self.assertEqual([Decimal(item["output"]["result"]) for item in lines],VALUES)

'''),
("offline_markdown_table",
'''def markdown_export(rows):
    batch=calculate_batch(rows)
    def esc(value):
        return str(value).replace("\\\\","\\\\\\\\").replace("|","\\\\|").replace("\\n"," ")
    head=[*NAMES,"result","unit"]
    lines=["| "+" | ".join(head)+" |","| "+" | ".join("---" for _ in head)+" |"]
    for inputs,output in zip(rows,batch["results"]):
        lines.append("| "+" | ".join(esc(v) for v in
                     [*(inputs[name] for name in NAMES),output["result"],output["unit"]])+" |")
    return "\\n".join(lines)+"\\n"

''',
'''    def test_g05_markdown_export(self):
        page=markdown_export(ROWS)
        self.assertIn("result | unit",page)
        self.assertEqual(len(page.splitlines()),4)

'''),
("escaped_accessible_html_table",
'''def html_export(rows):
    batch=calculate_batch(rows)
    head=[*NAMES,"result","unit"]
    th="".join("<th scope=\\"col\\">"+html.escape(str(x),quote=True)+"</th>" for x in head)
    body=[]
    for inputs,result in zip(rows,batch["results"]):
        items=[*(inputs[name] for name in NAMES),result["result"],result["unit"]]
        body.append("<tr>"+"".join("<td>"+html.escape(str(x),quote=True)+"</td>" for x in items)+"</tr>")
    return '<table aria-label="Validated calculations"><thead><tr>'+th+'</tr></thead><tbody>'+ "".join(body)+"</tbody></table>"

''',
'''    def test_g06_html_export(self):
        page=html_export(ROWS)
        self.assertIn('aria-label="Validated calculations"',page)
        self.assertEqual(page.count("<tr>"),3)
        self.assertNotIn("<script",page.lower())

'''),
("input_grouped_totals",
'''def group_totals(rows,field):
    if field not in NAMES:raise ValueError("UNKNOWN_GROUP_FIELD")
    batch=calculate_batch(rows)
    groups={}
    with localcontext() as context:
        context.prec=40
        for inputs,answer in zip(rows,batch["results"]):
            key=str(Decimal(str(inputs[field])))
            if key not in groups:groups[key]=[0,Decimal(0)]
            groups[key][0]+=1
            groups[key][1]+=Decimal(answer["result"])
    return [{"value":key,"count":v[0],"total":str(v[1])} for key,v in sorted(groups.items())]

''',
'''    def test_g07_grouped_totals(self):
        groups=group_totals(ROWS,NAMES[0])
        self.assertEqual(sum(item["count"] for item in groups),2)
        with localcontext() as context:
            context.prec=40
            self.assertEqual(sum((Decimal(item["total"]) for item in groups),Decimal(0)),sum(VALUES,Decimal(0)))
        with self.assertRaises(ValueError):group_totals(ROWS,"untrusted")

'''),
("exact_median",
'''def median_result(rows):
    values=sorted(Decimal(item["result"]) for item in calculate_batch(rows)["results"])
    midpoint=len(values)//2
    with localcontext() as context:
        context.prec=40
        median=values[midpoint] if len(values)%2 else (values[midpoint-1]+values[midpoint])/2
    return {"median":str(median),"count":len(values)}

''',
'''    def test_g08_exact_median(self):
        median=median_result(ROWS)
        with localcontext() as context:
            context.prec=40
            expected=(VALUES[0]+VALUES[1])/2
        self.assertEqual(Decimal(median["median"]),expected)

'''),
("population_variance",
'''def population_variance(rows):
    values=[Decimal(item["result"]) for item in calculate_batch(rows)["results"]]
    with localcontext() as context:
        context.prec=40
        mean=sum(values,Decimal(0))/len(values)
        variance=sum(((v-mean)**2 for v in values),Decimal(0))/len(values)
    return {"variance":str(variance),"unit_squared":True,"count":len(values)}

''',
'''    def test_g09_population_variance(self):
        with localcontext() as context:
            context.prec=40
            expected=((VALUES[0]-VALUES[1])**2)/4
        actual=Decimal(population_variance(ROWS)["variance"])
        self.assertLessEqual(abs(actual-expected),Decimal("1e-30"))

'''),
("population_standard_deviation",
'''def population_standard_deviation(rows):
    variance=Decimal(population_variance(rows)["variance"])
    with localcontext() as context:
        context.prec=40
        deviation=variance.sqrt()
    return {"standard_deviation":str(deviation),"unit":calculate_batch(rows)["results"][0]["unit"]}

''',
'''    def test_g10_population_standard_deviation(self):
        std=Decimal(population_standard_deviation(ROWS)["standard_deviation"])
        variance=Decimal(population_variance(ROWS)["variance"])
        with localcontext() as context:
            context.prec=40
            tolerance=Decimal("1e-30")*max(Decimal(1),abs(variance))
            self.assertLessEqual(abs(std*std-variance),tolerance)
        self.assertGreaterEqual(std,Decimal(0))

''')
]

def checksum(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(65536),b""):h.update(block)
    return h.hexdigest()

def read(path):
    path=Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size>2_000_000:
        raise ValueError("TEN_UNTRUSTED_JSON")
    value=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(value,dict):raise ValueError("TEN_JSON_OBJECT_REQUIRED")
    return value

def safe_directory(folder):
    folder=Path(folder)
    if folder.exists() and (folder.is_symlink() or not folder.is_dir()):
        raise ValueError("TEN_UNSAFE_DIRECTORY")
    folder.mkdir(parents=True,mode=0o700,exist_ok=True)
    os.chmod(folder,0o700)
    return folder

def copy_verified(source,target):
    if source.is_symlink() or not source.is_dir():raise ValueError("TEN_UNSAFE_SOURCE")
    total=0;number=0
    for item in source.rglob("*"):
        if item.is_symlink():raise ValueError("TEN_SOURCE_SYMLINK")
        if item.is_file():
            number+=1;total+=item.stat().st_size
            if number>64 or total>8_000_000:raise ValueError("TEN_SOURCE_SIZE_CAP")
        elif not item.is_dir():raise ValueError("TEN_SOURCE_NONREGULAR")
    shutil.copytree(source,target,symlinks=False)

def load_maker(path):
    path=Path(path)
    if not path.is_file() or path.is_symlink():raise ValueError("TEN_VERIFIED_MAKER_REQUIRED")
    spec=importlib.util.spec_from_file_location("ten_generation_maker",path)
    maker=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maker)
    return maker

def original_identity(source,maker):
    if not RECIPE.fullmatch(source.name) or source.is_symlink():raise ValueError("TEN_COMPILER_RECIPE_REQUIRED")
    request=read(source/"design_request.json")
    receipt=read(source/"design_receipt.json")
    digest=hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
    revision=receipt.get("generator_capability_revision")
    if (receipt.get("schema")!="saeit.factory.synthesis-receipt.v1"
        or receipt.get("request_sha256")!=digest or receipt.get("recipe")!=source.name
        or revision not in REVISIONS
        or receipt.get("family_id") not in ("F27","F28")
        or receipt.get("family_id")!=request.get("family_id")):
        raise ValueError("TEN_COMPILER_PROVENANCE_NOT_VERIFIED")
    name,files=maker.inspect_recipe(source)
    if "generation_features.py" in files or "test_generation_features.py" in files:
        raise ValueError("TEN_SOURCE_ALREADY_CUSTOMIZED")
    calculator=(source/"calculator.py").read_text(encoding="utf8")
    if (not calculator.startswith('"""Generated deterministic arithmetic planning tool;')
        or "# STATS_API_V3_START" not in calculator
        or REVISIONS[revision] not in calculator
        or (revision=="verified-summary-v3" and "# DISTRIBUTION_API_V4_START" in calculator)):
        raise ValueError("TEN_VERIFIED_COMPILER_SOURCE_REQUIRED")
    maker.verify_recipe(source,minimum_tests=7)
    return maker.source_digest(source,files),receipt["family_id"]

def generation_root(private,source):
    """Keep original v3 lineages untouched when source upgrades to v4."""
    source=Path(source)
    revision=read(source/"design_receipt.json").get("generator_capability_revision")
    if revision not in REVISIONS:
        raise ValueError("TEN_UNSUPPORTED_COMPILER_REVISION")
    legacy=Path(private)/"quality-excellence"/"ten-generations"/source.name
    return legacy if revision=="verified-summary-v3" else legacy/revision

def generate_feature_files(source,generation):
    if type(generation) is not int or not 1<=generation<=10:raise ValueError("TEN_GENERATION_RANGE")
    functions=HEADER+"".join(item[1] for item in FEATURES[:generation])
    tests=TEST_HEADER+"".join(item[2] for item in FEATURES[:generation])
    (source/"generation_features.py").write_text(functions,encoding="utf8")
    (source/"test_generation_features.py").write_text(tests,encoding="utf8")
    with (source/"README.md").open("a",encoding="utf8") as f:
        f.write("\nGeneration %02d validated technical feature: %s.\n"%(generation,FEATURES[generation-1][0]))
    for name in ("generation_features.py","test_generation_features.py"):
        os.chmod(source/name,0o600)

def verify_prior(parent,recipe,gen,maker,upstream_hash):
    folder=parent/("g%02d"%gen)
    receipt=read(folder/"receipt.json")
    if (receipt.get("schema")!=SCHEMA or receipt.get("generation")!=gen
        or receipt.get("recipe")!=recipe or receipt.get("upstream_source_sha256")!=upstream_hash
        or receipt.get("feature")!=FEATURES[gen-1][0]
        or receipt.get("commercial_release") is not False
        or receipt.get("quality_1000_certified") is not False):
        raise ValueError("TEN_GENERATION_RECEIPT_CONFLICT")
    source=folder/"source"/recipe
    if maker.source_digest(source,maker.inspect_recipe(source)[1])!=receipt.get("source_sha256"):
        raise ValueError("TEN_GENERATION_SOURCE_TAMPERED")
    bundle=folder/"product"/recipe/(recipe+"-internal-qa.zip")
    manifest=read(folder/"product"/recipe/"manufacturing_manifest.json")
    if (checksum(bundle)!=receipt.get("artifact_sha256")
        or manifest.get("source_sha256")!=receipt["source_sha256"]
        or manifest.get("artifact_sha256")!=receipt["artifact_sha256"]
        or manifest.get("qa_status")!="passed"
        or manifest.get("public_listing_enabled") is not False):
        raise ValueError("TEN_GENERATION_ARTIFACT_TAMPERED")
    return receipt

def one_line(source,private,maker):
    source=Path(source)
    original_hash,family=original_identity(source,maker)
    work=safe_directory(generation_root(private,source))
    previous_source=source;previous_hash=original_hash
    new=[]
    for gen in range(1,11):
        target=work/("g%02d"%gen)
        if target.exists() or target.is_symlink():
            proof=verify_prior(work,source.name,gen,maker,previous_hash)
        else:
            staging=Path(tempfile.mkdtemp(prefix=".gen%02d-"%gen,dir=str(work)))
            try:
                new_source_root=safe_directory(staging/"source")
                new_source=new_source_root/source.name
                copy_verified(previous_source,new_source)
                generate_feature_files(new_source,gen)
                name,files=maker.inspect_recipe(new_source)
                new_hash=maker.source_digest(new_source,files)
                if new_hash==previous_hash:raise RuntimeError("TEN_NO_REAL_SOURCE_IMPROVEMENT")
                measurements={}
                maker.verify_recipe(new_source,evidence=measurements,minimum_tests=7+gen)
                product=maker.manufacture(source.name,new_source_root,staging/"product")
                manifest=read(staging/"product"/source.name/"manufacturing_manifest.json")
                archive=staging/"product"/source.name/(source.name+"-internal-qa.zip")
                archive_hash=checksum(archive)
                if (product.get("qa_status")!="passed"
                    or manifest.get("source_sha256")!=new_hash
                    or manifest.get("artifact_sha256")!=archive_hash
                    or manifest.get("public_listing_enabled") is not False
                    or manifest.get("professional_quality_approved") is not False):
                    raise RuntimeError("TEN_REAL_PRODUCT_QA_FAILED")
                proof={"schema":SCHEMA,"recipe":source.name,"family_id":family,
                       "generation":gen,"feature":FEATURES[gen-1][0],
                       "upstream_source_sha256":previous_hash,"source_sha256":new_hash,
                       "artifact_sha256":archive_hash,
                       "independently_executed_tests":measurements["successful_tests"],
                       "technical_qa":"passed","quality_1000_certified":False,
                       "commercial_release":False,"public_listing_enabled":False}
                receipt=staging/"receipt.json"
                receipt.write_text(json.dumps(proof,sort_keys=True,indent=2)+"\n",encoding="utf8")
                os.chmod(receipt,0o600)
                staging.rename(target)
                new.append({"generation":gen,"feature":proof["feature"],
                            "artifact_sha256":archive_hash,"tests":measurements["successful_tests"]})
            finally:
                if staging.exists():shutil.rmtree(staging)
        previous_source=target/"source"/source.name
        previous_hash=proof["source_sha256"]
    if maker.source_digest(source,maker.inspect_recipe(source)[1])!=original_hash:
        raise RuntimeError("TEN_ORIGINAL_SOURCE_CHANGED")
    return {"recipe":source.name,"family_id":family,
            "completed_verified_generations":10,"new_generations_this_run":len(new),
            "new":new,"commercial_release":False,"quality_1000_certified":False}

def run(private,sources,maker_path,*,limit=2):
    private=Path(private).expanduser().resolve()
    sources=Path(sources).expanduser().resolve()
    if not private.is_dir() or private.is_symlink() or not sources.is_dir() or sources.is_symlink():
        raise ValueError("TEN_PRIVATE_FACTORY_ROOTS_REQUIRED")
    if type(limit) is not int or not 1<=limit<=2:raise ValueError("TEN_BOUNDED_PRODUCT_LIMIT")
    maker=load_maker(maker_path)
    lock=safe_directory(private/"quality-excellence"/"ten-generations")/".ten-generation.lock"
    with lock.open("a+b") as handle:
        fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
        eligible=[];issues=[]
        for source in sorted(sources.iterdir()):
            if not source.is_dir() or source.is_symlink() or not RECIPE.fullmatch(source.name):continue
            try:
                identity,family=original_identity(source,maker)
                eligible.append((source,family))
            except (RuntimeError,ValueError,OSError) as error:
                issues.append({"recipe":source.name,"reason":str(error)[:120]})
        # Serve both actual tool families where available; skip fully verified
        # families before taking more work and never overwrite source originals.
        selected=[]
        for family in ("F27","F28"):
            options=[s for s,f in eligible if f==family]
            options.sort(key=lambda s:((
                generation_root(private,s)/"g10"/"receipt.json"
            ).is_file(),s.name))
            if options and len(selected)<limit:selected.append(options[0])
        completed=[]
        for source in selected:
            completed.append(one_line(source,private,maker))
        return {"schema":SCHEMA,"eligible_compiler_owned_sources":len(eligible),
                "selected":len(selected),"completed":completed,"untrusted_sources":issues[:20],
                "new_real_generations":sum(p["new_generations_this_run"] for p in completed),
                "ten_generation_lineages_verified":sum(p["completed_verified_generations"]==10 for p in completed),
                "other_38_families_not_proven":True,
                "professional_1000_approved":False,"public_uploads":0,"website_changes":0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--private-root",required=True)
    p.add_argument("--source-root",required=True)
    p.add_argument("--maker",required=True)
    p.add_argument("--limit",type=int,default=2)
    args=p.parse_args()
    result=run(args.private_root,args.source_root,args.maker,limit=args.limit)
    print("FACTORY_TEN_GENERATIONS="+json.dumps(result,sort_keys=True))
    print("FACTORY_TEN_REAL_GENERATION_BUILDS="+str(result["new_real_generations"]))
    print("FACTORY_TEN_GENERATIONS_1000_CERTIFICATIONS=0")
    print("FACTORY_TEN_GENERATIONS_PUBLIC_RELEASES=0")
if __name__=="__main__":main()
