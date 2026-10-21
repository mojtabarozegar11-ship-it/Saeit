#!/usr/bin/env python3
"""F19: ten additive, tested customer capabilities from one proven BUILD50 template.

All editions are private noncommercial candidates; existing source and sites are immutable.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

PRODUCT="saas_launch_starter_2026"
SCHEMA="saeit.factory.f19-ten-functional-generations.v1"
FILES=("LICENSE.txt","README.md","index.html","styles.css")
HEADER='''"""Offline customer customization tools for the verified F19 web template."""
import html
import io
import re
import zipfile
from urllib.parse import urlsplit
from xml.sax.saxutils import escape as xml_escape

def _text(value,maximum=120):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum or any(ord(c)<32 for c in value):
        raise ValueError("INVALID_CUSTOMER_TEXT")
    return value.strip()

def _origin(url):
    u=urlsplit(_text(url,240))
    if u.scheme!="https" or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ("","/"):
        raise ValueError("HTTPS_SITE_ORIGIN_REQUIRED")
    return "https://"+u.netloc.lower().rstrip("/")

'''
TEST_HEADER='''import io
from pathlib import Path
import unittest
from zipfile import ZipFile
import site_tools as t

HTML=(Path(__file__).parent/"index.html").read_text(encoding="utf8")
CSS=(Path(__file__).parent/"styles.css").read_text(encoding="utf8")
class CustomerCapabilities(unittest.TestCase):
'''
FEATURES=[
("safe_brand_personalization",
'''def brand_personalize(page,name):
    safe=html.escape(_text(name,70),quote=True)
    if "Northstar Studio" not in page:raise ValueError("BASE_BRAND_NOT_FOUND")
    return page.replace("Northstar Studio",safe)

''',
'''    def test_g01_brand(self):
        result=t.brand_personalize(HTML,"Orchid & Co")
        self.assertIn("Orchid &amp; Co",result)
        self.assertNotIn("Northstar Studio",result)
        with self.assertRaises(ValueError):t.brand_personalize(HTML,"")

'''),
("safe_page_title",
'''def page_title(page,title):
    safe=html.escape(_text(title,110),quote=True)
    new,count=re.subn(r"<title>[^<]*</title>","<title>"+safe+"</title>",page,count=1)
    if count!=1:raise ValueError("TITLE_ELEMENT_REQUIRED")
    return new

''',
'''    def test_g02_title(self):
        out=t.page_title(HTML,"My <Brand>")
        self.assertIn("<title>My &lt;Brand&gt;</title>",out)
        self.assertNotIn("<title>My <Brand>",out)
        with self.assertRaises(ValueError):t.page_title("missing","hello")

'''),
("safe_search_description",
'''def meta_description(page,description):
    safe=html.escape(_text(description,170),quote=True)
    pattern=r'(<meta name="description" content=")[^"]*(">)'
    updated,n=re.subn(pattern,lambda m:m.group(1)+safe+m.group(2),page,count=1)
    if n!=1:raise ValueError("META_DESCRIPTION_REQUIRED")
    return updated

''',
'''    def test_g03_description(self):
        out=t.meta_description(HTML,'A "clear" service & pricing')
        self.assertIn('A &quot;clear&quot; service &amp; pricing',out)
        with self.assertRaises(ValueError):t.meta_description(HTML,"x"*171)

'''),
("contrast_aware_button_palette",
'''def button_palette(css,hex_color):
    if not isinstance(hex_color,str) or not re.fullmatch(r"#[0-9a-fA-F]{6}",hex_color):
        raise ValueError("HEX_COLOR_REQUIRED")
    values=[int(hex_color[i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
    light=.2126*linear[0]+.7152*linear[1]+.0722*linear[2]
    foreground="#000000" if (light+.05)/.05>=4.5 else "#ffffff"
    return css+"\\n.btn-primary{background:"+hex_color+";color:"+foreground+";}\\n"

''',
'''    def test_g04_button_palette(self):
        self.assertIn("color:#ffffff",t.button_palette(CSS,"#000000"))
        self.assertIn("color:#000000",t.button_palette(CSS,"#ffffff"))
        with self.assertRaises(ValueError):t.button_palette(CSS,"red;url(x)")

'''),
("safe_email_contact_link",
'''def email_contact(page,address):
    valid=re.fullmatch(r"[A-Za-z0-9._%+\\-]{1,64}@[A-Za-z0-9\\-]+(?:\\.[A-Za-z0-9\\-]+)+",str(address))
    if not valid or len(address)>254:raise ValueError("INVALID_CONTACT_EMAIL")
    if page.count("</main>")!=1:raise ValueError("MAIN_CONTENT_REQUIRED")
    link='<p class="template-email-contact"><a href="mailto:'+address+'">Contact by email</a></p>'
    return page.replace("</main>",link+"\\n</main>",1)

''',
'''    def test_g05_email_link(self):
        out=t.email_contact(HTML,"team@example.org")
        self.assertIn('href="mailto:team@example.org"',out)
        self.assertEqual(out.count("</main>"),1)
        with self.assertRaises(ValueError):t.email_contact(HTML,'foo" onclick="bad')

'''),
("print_readiness",
'''def print_stylesheet(css):
    return css+"\\n@media print{nav,.hero-panel,.hero-actions{display:none!important}body{color:#000!important;background:#fff!important}a{text-decoration:underline}main{max-width:100%}}\\n"

''',
'''    def test_g06_print(self):
        out=t.print_stylesheet(CSS)
        self.assertIn("@media print",out)
        self.assertIn("display:none!important",out)
        self.assertEqual(out.count("{"),out.count("}"))

'''),
("right_to_left_layout_support",
'''def rtl_support(css):
    return css+'\\nhtml[dir="rtl"]{direction:rtl;text-align:right}html[dir="rtl"] .nav-wrap{flex-direction:row-reverse}html[dir="rtl"] .hero-grid{direction:rtl}\\n'

''',
'''    def test_g07_rtl(self):
        out=t.rtl_support(CSS)
        self.assertIn('html[dir="rtl"]',out)
        self.assertEqual(out.count("{"),out.count("}"))

'''),
("minimal_https_sitemap",
'''def sitemap_xml(site_origin):
    origin=_origin(site_origin)
    return '<?xml version="1.0" encoding="UTF-8"?>\\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>'+xml_escape(origin+'/')+'</loc></url></urlset>\\n'

''',
'''    def test_g08_sitemap(self):
        self.assertIn("https://example.org/",t.sitemap_xml("https://example.org"))
        with self.assertRaises(ValueError):t.sitemap_xml("http://example.org")
        with self.assertRaises(ValueError):t.sitemap_xml("https://user:pass@example.org")

'''),
("minimal_https_robots",
'''def robots_txt(site_origin):
    origin=_origin(site_origin)
    return "User-agent: *\\nAllow: /\\nSitemap: "+origin+"/sitemap.xml\\n"

''',
'''    def test_g09_robots(self):
        self.assertIn("Sitemap: https://example.org/sitemap.xml",t.robots_txt("https://example.org/"))
        with self.assertRaises(ValueError):t.robots_txt("javascript:alert(1)")

'''),
("deterministic_customer_site_zip",
'''def package_website(files):
    allowed={"index.html","styles.css","sitemap.xml","robots.txt"}
    if not isinstance(files,dict) or not {"index.html","styles.css"}.issubset(files) or not set(files)<=allowed:
        raise ValueError("SITE_PACKAGE_ALLOWLIST_REQUIRED")
    data=io.BytesIO()
    with zipfile.ZipFile(data,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            body=files[name]
            if not isinstance(body,str) or not body or len(body.encode("utf8"))>2_000_000:
                raise ValueError("SITE_PACKAGE_INVALID_BYTES")
            info=zipfile.ZipInfo("my-website/"+name,date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            archive.writestr(info,body.encode("utf8"))
    return data.getvalue()

''',
'''    def test_g10_zip(self):
        one=t.package_website({"index.html":HTML,"styles.css":CSS})
        self.assertEqual(one,t.package_website({"styles.css":CSS,"index.html":HTML}))
        with ZipFile(io.BytesIO(one)) as z:
            self.assertEqual(set(z.namelist()),{"my-website/index.html","my-website/styles.css"})
            self.assertEqual(z.testzip(),None)
        with self.assertRaises(ValueError):t.package_website({"../hack":"yes","index.html":HTML,"styles.css":CSS})

''')
]

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(65536),b""):h.update(chunk)
    return h.hexdigest()

def load_protocol(path):
    path=Path(path)
    if not path.is_file() or path.is_symlink():raise ValueError("F19_PROOF_PROTOCOL_REQUIRED")
    spec=importlib.util.spec_from_file_location("f19_ten_proof_protocol",str(path))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def read(path):
    path=Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size>2_000_000:
        raise ValueError("F19_UNTRUSTED_RECEIPT")
    return json.loads(path.read_text(encoding="utf8"))

def original(private,protocol):
    folder=private/"digital-products"/PRODUCT
    home=private/"build-50"/PRODUCT
    manifest=read(folder/"manufacturing_manifest.json")
    state=read(home/"state.json")
    archive=folder/(PRODUCT+"-internal-qa.zip")
    if (manifest.get("family_id")!="F19" or manifest.get("recipe")!=PRODUCT
        or manifest.get("qa_status")!="passed" or manifest.get("public_listing_enabled") is not False
        or manifest.get("owner_publication_approval") is not False
        or manifest.get("independent_human_review") is not False
        or manifest.get("artifact_sha256")!=digest(archive)
        or manifest.get("build50_source_snapshot_sha256")!=state.get("source_snapshot_sha256")
        or not protocol.verify_attempt(home,state,state["source_snapshot_sha256"])):
        raise ValueError("F19_ORIGINAL_50_STAGE_PROOF_INVALID")
    original_folder=Path(state["attempt_folder"])
    review=read(original_folder/"independent-technical-review.json")
    if review.get("checks_passed")!=10 or review.get("human_professional_review_done") is not False:
        raise ValueError("F19_INDEPENDENT_TECHNICAL_REVIEW_REQUIRED")
    with zipfile.ZipFile(archive) as z:
        expected={PRODUCT+"/"+name for name in FILES}
        if set(z.namelist())!=expected or z.testzip() is not None:
            raise ValueError("F19_ORIGINAL_ZIP_INVALID")
        source={name:z.read(PRODUCT+"/"+name) for name in FILES}
        if any(len(v)>2_000_000 for v in source.values()):raise ValueError("F19_ORIGINAL_FILE_TOO_LARGE")
    return archive,source

def versions(generation):
    if type(generation) is not int or generation not in range(1,11):
        raise ValueError("F19_GENERATION_OUT_OF_RANGE")
    code=HEADER+"".join(feature[1] for feature in FEATURES[:generation])
    tests=TEST_HEADER+"".join(feature[2] for feature in FEATURES[:generation])
    return code,tests

def validate_customer_tools(folder,generation,original_assets):
    code,tests=versions(generation)
    for name,contents in original_assets.items():
        (folder/name).write_bytes(contents)
    (folder/"site_tools.py").write_text(code,encoding="utf8")
    (folder/"test_site_tools.py").write_text(tests,encoding="utf8")
    test_cmd=("import unittest,json,sys;"
              "suite=unittest.defaultTestLoader.discover('.',pattern='test_site_tools.py');"
              "result=unittest.TestResult();suite.run(result);"
              "print(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)}));"
              "sys.exit(0 if result.wasSuccessful() else 1)")
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1")
    test=subprocess.run([sys.executable,"-B","-c",test_cmd],cwd=folder,
                        env=env,text=True,capture_output=True,timeout=90,check=False)
    if test.returncode!=0:
        raise ValueError("F19_REAL_FEATURE_TEST_FAILURE:"+test.stderr[-500:])
    line=json.loads(test.stdout.strip().splitlines()[-1])
    if line!={"tests":generation,"failures":0,"errors":0,"skipped":0}:
        raise ValueError("F19_FEATURE_TEST_COUNT_MISMATCH")
    return line["tests"]

def zip_customer_tools(folder,target,generation,original_assets):
    code,tests=versions(generation)
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED) as z:
        all_files={**original_assets,"site_tools.py":code.encode(),"test_site_tools.py":tests.encode()}
        for name in sorted(all_files):
            info=zipfile.ZipInfo(PRODUCT+"/"+name,date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            z.writestr(info,all_files[name])
    with zipfile.ZipFile(target) as z:
        if z.testzip() is not None or set(z.namelist())!={PRODUCT+"/"+x for x in all_files}:
            raise ValueError("F19_GENERATION_ARCHIVE_INVALID")
        for name,blob in all_files.items():
            if z.read(PRODUCT+"/"+name)!=blob:
                raise ValueError("F19_GENERATION_CONTENT_HASH_CONFLICT")

def check_existing(folder,generation,prior_hash,original_assets):
    r=read(folder/"receipt.json")
    archive=folder/(PRODUCT+"-g%02d-internal-qa.zip"%generation)
    if (r.get("schema")!=SCHEMA or r.get("generation")!=generation
        or r.get("feature")!=FEATURES[generation-1][0]
        or r.get("upstream_archive_sha256")!=prior_hash
        or r.get("archive_sha256")!=digest(archive)
        or r.get("measured_tests")!=generation
        or r.get("commercial_release") is not False
        or r.get("quality_1000_certified") is not False):
        raise ValueError("F19_EXISTING_RECEIPT_CONFLICT")
    with tempfile.TemporaryDirectory(prefix="f19-verify-") as d:
        wanted=Path(d)/"repro.zip"
        zip_customer_tools(Path(d),wanted,generation,original_assets)
        if digest(wanted)!=r["archive_sha256"]:
            raise ValueError("F19_EXISTING_EDITION_TAMPERED")
    return r["archive_sha256"]

def run(private,protocol_file):
    private=Path(private).expanduser().resolve()
    if not private.is_dir() or private.is_symlink():raise ValueError("F19_PRIVATE_ROOT_REQUIRED")
    proto=load_protocol(protocol_file)
    original_archive,assets=original(private,proto)
    baseline=digest(original_archive)
    root=private/"quality-excellence"/"f19-ten-generations"/baseline[:24]
    if any(p.is_symlink() for p in (root.parent,root)) or (root.exists() and not root.is_dir()):
        raise ValueError("F19_UNSAFE_GENERATION_ROOT")
    root.mkdir(parents=True,mode=0o700,exist_ok=True)
    lock=root/".generation.lock"
    if lock.is_symlink():raise ValueError("F19_UNSAFE_LOCK")
    new=[]
    with lock.open("a+b") as handle:
        os.fchmod(handle.fileno(),0o600)
        fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
        upstream=baseline
        for gen in range(1,11):
            dst=root/("g%02d"%gen)
            if dst.exists() or dst.is_symlink():
                if dst.is_symlink() or not dst.is_dir():raise ValueError("F19_UNSAFE_EXISTING_GENERATION")
                upstream=check_existing(dst,gen,upstream,assets)
                continue
            stage=Path(tempfile.mkdtemp(prefix=".f19-g%02d-"%gen,dir=str(root)))
            try:
                tests=validate_customer_tools(stage,gen,assets)
                product=stage/(PRODUCT+"-g%02d-internal-qa.zip"%gen)
                zip_customer_tools(stage,product,gen,assets)
                edition_hash=digest(product)
                receipt={"schema":SCHEMA,"family_id":"F19","generation":gen,
                         "feature":FEATURES[gen-1][0],"upstream_archive_sha256":upstream,
                         "archive_sha256":edition_hash,"original_source_sha256":baseline,
                         "measured_tests":tests,"technical_qa":"passed",
                         "quality_1000_certified":False,"commercial_release":False,
                         "public_listing_enabled":False}
                (stage/"receipt.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n",encoding="utf8")
                stage.rename(dst)
                new.append({"generation":gen,"feature":receipt["feature"],
                            "archive_sha256":edition_hash,"tests":tests})
                upstream=edition_hash
            finally:
                if stage.exists():shutil.rmtree(stage)
        if digest(original_archive)!=baseline:
            raise ValueError("F19_BASELINE_MUTATED_DURING_BUILD")
    return {"family_id":"F19","product_id":PRODUCT,"verified_generations":10,
            "new_generations_this_run":len(new),"new":new,
            "quality_1000_certified":False,"commercial_release":False}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--factory-private",required=True)
    parser.add_argument("--build50",required=True)
    args=parser.parse_args()
    print("F19_TEN_REAL_FUNCTIONAL_GENERATIONS="+json.dumps(run(args.factory_private,args.build50),sort_keys=True))
