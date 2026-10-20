#!/usr/bin/env python3
"""Independent source-specific deep technical diagnostics for returned MPW stock.

No arbitrary source code execution, HTTP, public site writes or invented reviews.
Per product: real ZIP/manifest source verification, native content parsing,
cryptographic per-member inventory and precise human acceptance requirements.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
import zlib

SCHEMA="mpw.factory.stage1-deep-evidence.v1"
RISK=("INDEPENDENT_CONTENT_QUALITY_REVIEW_REQUIRED",
      "OWNERSHIP_AND_ASSET_LICENSE_REVIEW_REQUIRED",
      "COMMERCIAL_PUBLICATION_APPROVAL_REQUIRED")
DOCX={"[Content_Types].xml","word/document.xml"}
XLSX={"[Content_Types].xml","xl/workbook.xml"}
EPUB={"mimetype","META-INF/container.xml"}

def must(ok,code):
    if not ok:raise ValueError("DEEP_QA_"+code)
def sha(b):return hashlib.sha256(b).hexdigest()
def private(p):
    p=Path(p)
    must(not p.is_symlink(),"UNSAFE_FOLDER")
    p.mkdir(parents=True,exist_ok=True,mode=0o700)
    must(p.is_dir() and not p.is_symlink(),"UNSAFE_FOLDER")
    os.chmod(p,0o700)
    return p
def put(p,obj):
    p=Path(p);private(p.parent);must(not p.is_symlink(),"UNSAFE_OUTPUT")
    raw=(json.dumps(obj,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode("utf8")
    if p.exists() and p.read_bytes()==raw:return False
    fd,tmp=tempfile.mkstemp(dir=str(p.parent),prefix=".deep-")
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o600);os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return True

def verify_pdf(raw):
    must(raw.startswith(b"%PDF-") and b"%%EOF" in raw[-2048:],"PDF_TRAILER")
    must(b"/Type" in raw and (b"/Page" in raw or b"/Pages" in raw),"PDF_PAGE_TREE")
    return "pdf_header_page_and_trailer"
def verify_png(raw):
    must(len(raw)>40 and raw[:8]==b"\x89PNG\r\n\x1a\n","PNG_MAGIC")
    pos=8;chunks=0;have_data=have_end=False
    while pos<len(raw):
        must(pos+12<=len(raw) and chunks<20000,"PNG_BROKEN_CHUNK")
        size=struct.unpack_from(">I",raw,pos)[0]
        must(size<=25_000_000 and pos+12+size<=len(raw),"PNG_CHUNK_SIZE")
        kind=raw[pos+4:pos+8];data=raw[pos+8:pos+8+size]
        crc=struct.unpack_from(">I",raw,pos+8+size)[0]
        must(zlib.crc32(kind+data)&0xffffffff==crc,"PNG_CRC")
        if chunks==0:must(kind==b"IHDR" and size==13,"PNG_IHDR")
        if kind==b"IDAT":have_data=True
        if kind==b"IEND":have_end=True;must(pos+12+size==len(raw),"PNG_TRAILING_BYTES")
        pos+=12+size;chunks+=1
        if have_end:break
    must(have_data and have_end,"PNG_INCOMPLETE_IMAGE")
    return "png_full_chunk_crc_and_structure"
def verify_woffice(raw,kind):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        files=set(z.namelist())
        expected={"docx":DOCX,"xlsx":XLSX,"epub":EPUB,"ods":{"mimetype","content.xml"}}[kind]
        must(expected<=files,"OFFICE_REQUIRED_PARTS")
        must(z.testzip() is None,"OFFICE_ZIP_CRC")
        if kind in ("docx","xlsx","ods"):
            for member in expected:
                if member.endswith(".xml"):
                    must(z.getinfo(member).file_size<8_000_000,"XML_TOO_LARGE")
                    ET.fromstring(z.read(member))
        elif kind=="epub":
            must(z.read("mimetype")==b"application/epub+zip","EPUB_MIMETYPE")
            ET.fromstring(z.read("META-INF/container.xml"))
    return kind+"_native_xml_members_and_crc"
def verify_wav(raw):
    must(len(raw)>=44 and raw[:4]==b"RIFF" and raw[8:12]==b"WAVE","WAV_HEADER")
    declared=struct.unpack_from("<I",raw,4)[0]+8
    must(declared<=len(raw) and declared>=36,"WAV_RIFF_LENGTH")
    pos=12;data_found=fmt_found=False
    while pos+8<=declared:
        ident=raw[pos:pos+4];n=struct.unpack_from("<I",raw,pos+4)[0]
        must(n<=declared-pos-8,"WAV_CHUNK_OVERFLOW")
        if ident==b"fmt ":fmt_found=True
        if ident==b"data" and n>0:data_found=True
        pos+=8+n+(n&1)
    must(fmt_found and data_found,"WAV_MISSING_AUDIO")
    return "wav_chunk_lengths_and_audio_data"
def verify_mp4(raw):
    must(len(raw)>=20,"MP4_TOO_SHORT")
    pos=0;found=set()
    while pos+8<=len(raw):
        n=struct.unpack_from(">I",raw,pos)[0];kind=raw[pos+4:pos+8];head=8
        if n==1:must(pos+16<=len(raw),"MP4_LARGE_HEADER");n=struct.unpack_from(">Q",raw,pos+8)[0];head=16
        elif n==0:n=len(raw)-pos
        must(n>=head and pos+n<=len(raw),"MP4_BROKEN_ATOM")
        found.add(kind);pos+=n
    must(b"ftyp" in found and b"moov" in found and b"mdat" in found,"MP4_ATOMS_MISSING")
    return "mp4_ftyp_movie_and_media_atom"
def validate_member(name,raw):
    ext=PurePosixPath(name).suffix.lower()
    if ext==".png":return verify_png(raw)
    if ext==".pdf":return verify_pdf(raw)
    if ext in (".docx",".epub",".xlsx",".ods"):return verify_woffice(raw,ext[1:])
    if ext==".wav":return verify_wav(raw)
    if ext==".mp4":return verify_mp4(raw)
    if ext==".json":
        obj=json.loads(raw.decode("utf8"))
        return "json_complete_parse"
    if ext==".svg":
        root=ET.fromstring(raw.decode("utf8"))
        must(root.tag.split("}")[-1].lower()=="svg","SVG_BAD_ROOT")
        return "svg_xml_root_parse"
    if ext in (".md",".txt",".html",".css",".js",".csv",".py"):
        raw.decode("utf-8-sig")
        return "full_utf8_decoding"
    return "static_signature_only_requires_native_specialist_review"

def review_archive(raw,courier):
    courier.safe_zip(raw)
    deep=[];unverified=[];issues=[];members=0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for info in archive.infolist():
            must(not info.is_dir() and info.file_size<=25*1024*1024,"SOURCE_MEMBER_TOO_LARGE")
            members+=1
            member=archive.read(info)
            try:
                method=validate_member(info.filename,member)
                if method.startswith("static_signature_only"):
                    unverified.append({"name":info.filename,"format":PurePosixPath(info.filename).suffix,
                                       "source_sha256":sha(member),"reason":method})
                else:
                    deep.append({"name":info.filename,"bytes":len(member),
                                 "source_sha256":sha(member),"test":method})
            except (ValueError,KeyError,TypeError,ET.ParseError,UnicodeError,
                    zipfile.BadZipFile,zlib.error) as exc:
                issues.append({"name":info.filename,"source_sha256":sha(member),
                               "reason":(type(exc).__name__+":"+str(exc))[:130]})
    must(len(deep)+len(unverified)+len(issues)==members,"MEMBER_ACCOUNTING")
    return {"source_members":members,"deep_native_checks_passed":len(deep),
            "source_format_specialist_required":len(unverified),
            "technical_defects_found":len(issues),"deep_passes":deep,
            "specialist_only":unverified,"technical_defects":issues}

def run(root,courier,repair):
    root=Path(root)
    must(root.is_dir() and not root.is_symlink(),"ROOT_UNAVAILABLE")
    sources=repair.stage1(root,courier)
    evidence=private(root/"design-state/mojplaywin-source-specific-reviews")
    result=[];totals=Counter()
    for source,row in sources:
        product=row.get("product_id");version=row.get("source_sha256")
        # Reuse the independent stock/return identity check from live courier.
        try:
            product,version,receipt,raw=repair.validate_original(root,source.name,row,courier)
            quality=review_archive(raw,courier)
            bad=quality["technical_defects_found"]
            status="technical_member_defects_need_new_source_build" if bad else (
               "native_specialist_functionality_test_required" if quality["source_format_specialist_required"]
               else "deep_technical_file_checks_pass_human_release_still_required")
            original_ok=True
        except (ValueError,TypeError,KeyError,OSError,RuntimeError,zipfile.BadZipFile) as exc:
            quality={"source_members":0,"deep_native_checks_passed":0,
              "source_format_specialist_required":0,"technical_defects_found":1,
              "deep_passes":[],"specialist_only":[],
              "technical_defects":[{"name":"original_archive","reason":str(exc)[:120]}]}
            status="source_integrity_or_structure_failed";original_ok=False
        row_out={"schema":SCHEMA,"tenant":"mojplaywin-main",
          "product_id":product,"source_sha256":version,"original_archive_valid":original_ok,
          "return_receipt_sha256":courier.digest(courier.json_blob(row)),
          "origin_artifact_sha256":row.get("artifact_sha256"),
          "quality":quality,"technical_status":status,
          "site_artifact_release_enabled":False,"requires_human_source_and_rights_review":True,
          "independent_reviewer_signature":None,
          "per_product_repair_tasks":[
            "Resolve every technical defect with a new source-bound version and rerun tests",
            "Perform domain-format runtime and device checks for specialist-only file types",
            "Supply actual verifiable editorial/scientific content review evidence",
            "Supply owner, supplier and third-party license/asset provenance",
            "Obtain explicit product-specific publication authorization after legal and payment QA"],
          "commercial_issue_codes":list(RISK),
          "customer_payment_enabled":False,"published":False,"return_work_closed":False}
        if not isinstance(product,str) or not isinstance(version,str):
            raise ValueError("DEEP_QA_BAD_IDENTITY")
        put(evidence/(product+"-"+version+".json"),row_out)
        result.append({"product_id":product,"status":status,"deep_checks":quality["deep_native_checks_passed"],
                       "missing_specialist_checks":quality["source_format_specialist_required"],
                       "defects":quality["technical_defects_found"]})
        totals["source_versions"]+=1
        totals["source_zips_verified"]+=int(original_ok)
        totals["deep_passed_files"]+=quality["deep_native_checks_passed"]
        totals["specialist_file_tests_remaining"]+=quality["source_format_specialist_required"]
        totals["technical_member_defects"]+=quality["technical_defects_found"]
    summary={"schema":SCHEMA,"checked_at_utc":datetime.now(timezone.utc).isoformat(),
      "tenant":"mojplaywin-main","returned_versions":len(sources),
      **dict(totals),"independent_human_signoffs_verified":0,
      "commercially_approved_versions":0,"stage1_returns_still_open":len(sources),
      "originals_modified":0,"sites_or_payments_changed":0,"results":result}
    put(evidence/"status.json",summary)
    print("MPW_DEEP_SOURCE_REWORK="+json.dumps({k:summary.get(k,0) for k in (
      "returned_versions","source_zips_verified","deep_passed_files",
      "specialist_file_tests_remaining","technical_member_defects",
      "independent_human_signoffs_verified","stage1_returns_still_open")},sort_keys=True))
    return summary
def main():
    p=argparse.ArgumentParser();p.add_argument("--factory-private",required=True)
    args=p.parse_args()
    import importlib.util
    base=Path(__file__).resolve().parent
    def load(module_name):
        spec=importlib.util.spec_from_file_location(module_name,str(base/(module_name+".py")))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    run(args.factory_private,load("mpw_vps_warehouse_courier"),load("mpw_factory_stage1_technical_repair"))
if __name__=="__main__":main()
