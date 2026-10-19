#!/usr/bin/env python3
"""Generate usable, versioned *consumer review candidates* from real factory QA.

No fake expert signatures, publication, prices, site writes, or inferred rights.
The customer archive contains a runnable program, verified worked example,
onboarding, clear limitations and exact package QA evidence. Python 3.8+.
"""
import argparse
from decimal import Decimal,InvalidOperation
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

SHA=re.compile(r"^[0-9a-f]{64}$")
RECIPE=re.compile(r"^(synth|sheet)_[a-f0-9]{24}$")
POLICY="saeit.factory.consumer-package.v1"
MAX_PRODUCT_SIZE=25*1024*1024
MAX_CANDIDATES=10000

def digest(path):
    value=hashlib.sha256()
    with path.open("rb") as fp:
        for part in iter(lambda:fp.read(65536),b""):value.update(part)
    return value.hexdigest()

def blob(data):
    return (json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf8")

def read(path,max_bytes=200000):
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=max_bytes:
        raise ValueError("CONSUMER_INPUT_UNSAFE")
    item=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(item,dict):raise ValueError("CONSUMER_JSON_OBJECT_REQUIRED")
    return item

def private(path):
    if path.is_symlink():raise ValueError("CONSUMER_SYMLINK_DIRECTORY")
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not path.is_dir() or path.is_symlink():raise ValueError("CONSUMER_DIRECTORY_UNSAFE")
    os.chmod(str(path),0o700)

def atomic_bytes(path,data):
    private(path.parent)
    if path.is_symlink():raise ValueError("CONSUMER_SYMLINK_TARGET")
    fd,tmp=tempfile.mkstemp(dir=str(path.parent),prefix=".consumer-")
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as writer:
            writer.write(data);writer.flush();os.fsync(writer.fileno())
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def candidate_source(root,recipe):
    generated=root/"generated-product-recipes"/recipe
    manufactured=root/"digital-products"/recipe
    if any(x.is_symlink() for x in (generated,manufactured)) or not generated.is_dir() or not manufactured.is_dir():
        raise ValueError("CONSUMER_SOURCE_DIRECTORY_MISSING")
    request=read(generated/"design_request.json")
    receipt=read(generated/"design_receipt.json")
    manifest=read(manufactured/"manufacturing_manifest.json")
    archive=manufactured/(recipe+"-internal-qa.zip")
    if archive.is_symlink() or not archive.is_file() or not 0<archive.stat().st_size<=MAX_PRODUCT_SIZE:
        raise ValueError("CONSUMER_SOURCE_ZIP_MISSING")
    if (request.get("schema")!="saeit.factory.design-request.v1"
            or request.get("family_id") not in ("F27","F28")
            or receipt.get("schema")!="saeit.factory.synthesis-receipt.v1"
            or receipt.get("recipe")!=recipe
            or receipt.get("family_id")!=request["family_id"]
            or receipt.get("request_sha256")!=hashlib.sha256(json.dumps(
               request,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()):
        raise ValueError("CONSUMER_DESIGN_PROVENANCE_INVALID")
    if (manifest.get("recipe")!=recipe or manifest.get("qa_status")!="passed"
            or manifest.get("qa_evidence")!="unit_tests_passed"
            or manifest.get("commercial_status")!="private_internal_qa_pass_not_published"
            or manifest.get("owner_publication_approval") is not False
            or manifest.get("public_listing_enabled") is not False
            or manifest.get("family_id")!=request["family_id"]
            or manifest.get("functional_sha256")!=receipt.get("functional_sha256")
            or not SHA.fullmatch(str(manifest.get("artifact_sha256","")))
            or digest(archive)!=manifest["artifact_sha256"]):
        raise ValueError("CONSUMER_MANUFACTURING_RECEIPT_FAILED")
    tests=manifest.get("qa_measurements",{})
    if type(tests.get("successful_tests")) is not int or tests["successful_tests"]<3:
        raise ValueError("CONSUMER_MEASURED_TESTS_REQUIRED")
    if type(receipt.get("heldout_examples_passed")) is not int or receipt["heldout_examples_passed"]<3:
        raise ValueError("CONSUMER_INDEPENDENT_HOLDOUT_REQUIRED")
    ledger=root/"qa-rework"/recipe/"ledger.json"
    if ledger.is_symlink():raise ValueError("CONSUMER_REWORK_LEDGER_UNSAFE")
    if ledger.exists():
        state=read(ledger)
        if state.get("schema")!="saeit.factory.qa-rework.v1" or state.get("current_status") in ("needs_rework","expert_review"):
            raise ValueError("CONSUMER_OPEN_QA_REWORK")
    filename_set=manifest.get("files")
    if not isinstance(filename_set,list) or not filename_set or len(filename_set)>80:
        raise ValueError("CONSUMER_SOURCE_FILE_INDEX_MISSING")
    with zipfile.ZipFile(archive) as z:
        actual=z.namelist()
        expected=[recipe+"/"+f for f in sorted(filename_set)]
        if actual!=expected or z.testzip() is not None:raise ValueError("CONSUMER_SOURCE_ZIP_CONTENT_MISMATCH")
        for entry in z.infolist():
            if entry.file_size>MAX_PRODUCT_SIZE or ((entry.external_attr>>16)&0o170000)==0o120000:
                raise ValueError("CONSUMER_SOURCE_UNSAFE_ZIP_MEMBER")
    # Recompute recipe hashes, not just trust the prior manufacturer receipt.
    maker_path=Path(__file__).with_name("factory_product_maker.py")
    if not maker_path.is_file():raise ValueError("CONSUMER_MANUFACTURER_VERIFIER_MISSING")
    spec=importlib.util.spec_from_file_location("consumer_maker_verify",maker_path)
    maker=importlib.util.module_from_spec(spec);spec.loader.exec_module(maker)
    _,files=maker.inspect_recipe(generated)
    if maker.source_digest(generated,files)!=manifest.get("source_sha256"):
        raise ValueError("CONSUMER_STALE_MANUFACTURED_SOURCE")
    expected_first=request.get("acceptance_examples",[None])[0]
    sample=read(generated/"example_inputs.json",10000)
    if not isinstance(expected_first,dict) or not isinstance(expected_first.get("inputs"),dict):
        raise ValueError("CONSUMER_BENCHMARK_REQUIRED")
    calc=generated/"calculator.py"
    if calc.is_symlink() or not calc.is_file():raise ValueError("CONSUMER_EXECUTABLE_MISSING")
    for row in [request["training_examples"][0],expected_first]:
        try:
            run=subprocess.run([sys.executable,"-B",str(calc)],
                               input=json.dumps(row["inputs"]),text=True,
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                               timeout=12,check=True,cwd=str(generated))
            output=json.loads(run.stdout)
            got=Decimal(output["result"]);want=Decimal(str(row["output"]))
            if not got.is_finite() or abs(got-want)>Decimal("1e-12")*max(Decimal(1),abs(want)):
                raise ValueError("CONSUMER_BUYER_SMOKE_RESULT_MISMATCH")
            if output["unit"]!=request["output_unit"]:
                raise ValueError("CONSUMER_OUTPUT_UNIT_MISMATCH")
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired,InvalidOperation,KeyError,TypeError,ValueError) as exc:
            raise ValueError("CONSUMER_BUYER_SMOKE_FAILED") from exc
    if set(sample)!=set(x["name"] for x in request.get("inputs",[])):
        raise ValueError("CONSUMER_SAMPLE_FIELDS_MISMATCH")
    return generated,request,receipt,manifest,archive

def buyer_files(source,request,receipt,manifest):
    title=request["title"].strip()
    inputs=request["inputs"]
    inputs_text="\n".join("- **"+f["name"]+"** ("+f["unit"]+"): "
        +str(f.get("minimum","unbounded"))+" to "+str(f.get("maximum","unbounded")) for f in inputs)
    notes=request["limitations"].strip()
    guide=("# "+title+" — User guide\n\n"
           +"**What it does:** "+request["problem"].strip()+"\n\n"
           +"This is an offline deterministic mathematical scenario calculator. "
           +"It uses only values you enter; it does not supply verified business, scientific, medical or market data.\n\n"
           +"## Requirements\nPython 3.8 or newer. No cloud account, subscription, API or network required.\n\n"
           +"## Installation\n1. Unzip this archive.\n2. Open a terminal in the `product` directory.\n"
           +"3. Review and edit `example_inputs.json` using measured real inputs.\n"
           +"4. Run `python calculator.py < example_inputs.json`.\n"
           +"5. Read the JSON result and the unit; repeat with your own inputs.\n\n"
           +"## Inputs and units\n"+inputs_text+"\n\n"
           +"## Output\nOne numerical result, expressed in **"+request["output_unit"]+"**.\n\n"
           +"## Limitations\n"+notes+"\n"
           +"The user is responsible for the accuracy and suitability of the inputs. "
           +"Floating point displays or rounded values must not substitute for qualified decisions.\n\n"
           +"## Technical verification\nMeasured unit tests: "+str(manifest["qa_measurements"]["successful_tests"])
           +". Independent held-out design examples: "+str(receipt["heldout_examples_passed"])
           +". This does not constitute independent domain, usability, legal or commercial approval.\n")
    summary=("# "+title+"\n\n"+request["problem"].strip()+"\n\n"
             +"**Format:** offline Python calculator"
             +(" and spreadsheet" if request["family_id"]=="F27" else "")+".\n"
             +"**Inputs:** user's own measured values.\n"
             +"**Availability:** private editorial and commercial review candidate only.\n"
             +"**Limitations:** "+notes+"\n"
             +"**Price:** not set. **Sales authorization:** pending.\n")
    files={
      "guide/START_HERE.md":guide.encode(),
      "description/STORE_LISTING_DRAFT.md":summary.encode(),
      "requirements/RUNTIME.md":b"Python 3.8+; offline standard-library calculator. Open a workbook in a compatible spreadsheet application if included. No installation of third-party libraries is required to run the Python calculator.\n",
      "license/REVIEW_REQUIRED.txt":b"NOT LICENSED FOR PUBLIC RESALE OR DISTRIBUTION. Independent ownership, third-party rights and release terms must be checked and authorized before any commercial publication.\n",
      "qa/TECHNICAL_VALIDATION.json":blob({"schema":"saeit.factory.buyer-smoke.v1",
          "technical_qa_passed":True,"consumer_cli_smoke_examples_passed":2,
          "measured_unit_tests":manifest["qa_measurements"]["successful_tests"],
          "independent_design_holdout_examples":receipt["heldout_examples_passed"],
          "commercial_review_passed":False,"scientific_review_passed":False,
          "final_50_stage_verified":False,"human_review_attested":False}),
      "preview/WORKED_EXAMPLE.json":blob(request["acceptance_examples"][0]),
      "images/README.md":b"Visual identity and artwork have not undergone design or licensing review. Do not display invented brand graphics.\n",
    }
    for name in ("calculator.py","example_inputs.json","README.md","test_calculator.py"):
        file=source/name
        if file.is_symlink() or not file.is_file():raise ValueError("CONSUMER_PRODUCT_FILE_MISSING:"+name)
        files["product/"+name]=file.read_bytes()
    if request["family_id"]=="F27":
        workbooks=sorted(source.glob("*.xlsx"))
        if not workbooks:raise ValueError("CONSUMER_SPREADSHEET_MISSING")
        for p in workbooks:
            if p.is_symlink() or p.stat().st_size>MAX_PRODUCT_SIZE or not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}",p.name):
                raise ValueError("CONSUMER_SPREADSHEET_UNSAFE")
            files["product/"+p.name]=p.read_bytes()
    checksum="".join(hashlib.sha256(body).hexdigest()+"  "+name+"\n" for name,body in sorted(files.items()))
    files["qa/SHA256SUMS.txt"]=checksum.encode()
    if len(files)>45 or sum(len(x) for x in files.values())>MAX_PRODUCT_SIZE:
        raise ValueError("CONSUMER_PACKAGE_TOO_LARGE")
    return files

def pack(root,recipe):
    if not RECIPE.fullmatch(recipe):raise ValueError("CONSUMER_RECIPE_INVALID")
    source,request,receipt,manifest,archive=candidate_source(root,recipe)
    data=buyer_files(source,request,receipt,manifest)
    version=manifest["source_sha256"]
    if not SHA.fullmatch(str(version)):raise ValueError("CONSUMER_VERSION_INVALID")
    target=root/"customer-packs"/recipe/version
    if target.is_symlink():raise ValueError("CONSUMER_EXISTING_VERSION_UNSAFE")
    archive_name="customer-package.zip"
    if target.exists():
        check=read(target/"candidate_manifest.json")
        buyer=target/archive_name
        if (check.get("factory_source_sha256")!=version
                or not SHA.fullmatch(str(check.get("package_sha256","")))
                or buyer.is_symlink() or not buyer.is_file() or digest(buyer)!=check["package_sha256"]):
            raise ValueError("CONSUMER_EXISTING_PACKAGE_CORRUPT")
        return dict(check,new=False)
    private(target.parent)
    stage=Path(tempfile.mkdtemp(prefix=".customer-",dir=str(target.parent)))
    try:
        import io
        with zipfile.ZipFile(stage/archive_name,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
            for name,body in sorted(data.items()):
                info=zipfile.ZipInfo(name,(2020,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o100644<<16
                z.writestr(info,body)
        with zipfile.ZipFile(stage/archive_name) as z:
            if z.testzip() is not None or z.namelist()!=sorted(data):
                raise ValueError("CONSUMER_CUSTOMER_ARCHIVE_TEST_FAILED")
            for name,body in data.items():
                if z.read(name)!=body:raise ValueError("CONSUMER_CUSTOMER_BYTES_MISMATCH")
        package_sha=digest(stage/archive_name)
        result={"schema":POLICY,"product_id":recipe,"family_id":request["family_id"],
                "name":request["title"],"factory_source_sha256":version,
                "factory_internal_zip_sha256":manifest["artifact_sha256"],
                "package_sha256":package_sha,"package_bytes":(stage/archive_name).stat().st_size,
                "functional_sha256":receipt["functional_sha256"],
                "consumer_cli_smoke_examples_passed":2,"technical_buyer_package_verified":True,
                "qa_files_hashed":len(data)-1,
                "consumer_guide_included":True,
                "independent_domain_review_completed":False,
                "human_attestation_completed":False,
                "rights_and_license_review_completed":False,
                "store_order_and_fulfillment_verified":False,
                "price":None,"commercial_release":False,
                "public_download_allowed":False,
                "eligible_for_commercial_listing":False}
        atomic_bytes(stage/"candidate_manifest.json",blob(result))
        (stage/archive_name).chmod(0o400)
        os.chmod(str(stage),0o700)
        os.replace(str(stage),str(target))
        return dict(result,new=True)
    finally:
        if stage.exists():
            import shutil
            shutil.rmtree(str(stage))

def cycle(root,limit=2):
    if type(limit) is not int or not 1<=limit<=10:raise ValueError("CONSUMER_WORK_BUDGET_INVALID")
    root=Path(root).expanduser().resolve()
    if root.is_symlink() or not root.is_dir():raise ValueError("CONSUMER_FACTORY_ROOT_UNSAFE")
    target=root/"customer-packs"
    private(target)
    products=root/"generated-product-recipes"
    if not products.is_dir() or products.is_symlink():raise ValueError("CONSUMER_GENERATED_RECIPES_MISSING")
    entries=sorted(p for p in products.iterdir() if RECIPE.fullmatch(p.name))
    if len(entries)>MAX_CANDIDATES:raise ValueError("CONSUMER_UNBOUNDED_RECIPE_SCAN")
    actions=[];errors=[];selected=0;already=0
    for source in entries:
        if selected>=limit:break
        # Existing versions are re-verified but do not consume scarce new-product
        # manufacturing capacity. Edited source yields a distinct version.
        try:
            v=read(source/"design_receipt.json")
            request=read(source/"design_request.json")
            # Do not read a manifest into a public release state; inspection is
            # performed again inside pack() after checking source files.
            receipt=read(root/"digital-products"/source.name/"manufacturing_manifest.json")
            version=receipt.get("source_sha256")
            existing=target/source.name/version if isinstance(version,str) and SHA.fullmatch(version) else None
            if existing and existing.exists():
                pack(root,source.name)
                already+=1
                continue
            selected+=1
            result=pack(root,source.name)
            actions.append({"product_id":source.name,"package_sha256":result["package_sha256"],
                            "new":result["new"],"technical_buyer_package_verified":True})
        except (RuntimeError,ValueError,OSError,zipfile.BadZipFile,subprocess.SubprocessError) as exc:
            errors.append({"product_id":source.name,"reason":str(exc)[:150],"return_to_stage":1})
    report={"schema":"saeit.factory.customer-packaging-status.v1",
            "new_buyer_usable_packages_this_tick":sum(bool(x["new"]) for x in actions),
            "customer_review_packages_ready_for_independent_review":len(actions)+already,
            "previous_versions_revalidated_this_tick":already,
            "blocked_for_rework":errors[:30],"actions":actions,
            "commercially_approved_products":0,"store_purchase_eligible_products":0,
            "publications":0}
    atomic_bytes(target/"status.json",blob(report))
    return report

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--max-new",type=int,default=2)
    a=p.parse_args(argv)
    result=cycle(a.factory_private,limit=a.max_new)
    print("FACTORY_REAL_CONSUMER_PACKAGES_NEW="+str(result["new_buyer_usable_packages_this_tick"]))
    print("FACTORY_REAL_CONSUMER_PACKAGES_REVIEW_CANDIDATES="+str(result["customer_review_packages_ready_for_independent_review"]))
    print("FACTORY_CONSUMER_REWORK="+str(len(result["blocked_for_rework"])))
    print("FACTORY_VERIFIED_PAID_SALES_READY=0")
    return 0
if __name__=="__main__":
    try:sys.exit(main())
    except (ValueError,OSError,RuntimeError) as error:
        print("FACTORY_CONSUMER_PACKAGING_BLOCKED="+str(error)[:160],file=sys.stderr)
        sys.exit(1)
