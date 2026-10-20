#!/usr/bin/env python3
"""Independent actual-byte pilot acceptance of F34, with commercial gates CLOSED.

This is not a license, human quality judgement, payment test or store release.
Only a private source-SHA-bound receipt is created. Stdlib Python 3.8+.
"""
import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import re
import struct
import tempfile
import xml.etree.ElementTree as ET
import zipfile
import zlib

PRODUCT="fieldwork_ui_48_icons"
SHA=re.compile(r"^[a-f0-9]{64}$")
NAME=re.compile(r"^[a-z][a-z0-9_]{1,50}$")
SVG_NS="{http://www.w3.org/2000/svg}"
SVG_TAGS={"svg","title","rect","polygon","polyline","circle","ellipse"}
DOCS={"README.md","LICENSE.txt","catalog.json","preview.html"}
BLOCKERS=[
    "HUMAN_VISUAL_ACCESSIBILITY_AND_USABILITY_ACCEPTANCE_MISSING",
    "ASSET_OWNERSHIP_AND_COMMERCIAL_RIGHTS_SIGNOFF_MISSING",
    "SKU_PRICE_CURRENCY_TAX_REFUND_AND_LICENSE_TERMS_NOT_APPROVED",
    "LIVE_STORE_RELEASE_MANIFEST_NOT_PROVED",
    "BUYER_CHECKOUT_PAYMENT_RECEIPT_AND_ENTITLEMENT_E2E_NOT_PROVED",
]

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def jsonbytes(obj):
    return (json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n").encode()

def read_json(path,cap=200000):
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=cap:
        raise ValueError("PILOT_UNSAFE_JSON_PATH")
    doc=json.loads(path.read_bytes())
    if not isinstance(doc,dict):
        raise ValueError("PILOT_JSON_OBJECT_EXPECTED")
    return doc

def png_check(raw):
    """Validate actual PNG CRC and exact bounded 256px RGBA scanline stream."""
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("PILOT_PNG_SIGNATURE")
    i=8;seen=Counter();data=[]
    while i<len(raw):
        if i+12>len(raw):raise ValueError("PILOT_PNG_TRUNCATED")
        size=struct.unpack_from(">I",raw,i)[0];kind=raw[i+4:i+8]
        if size>4000000 or i+12+size>len(raw):
            raise ValueError("PILOT_PNG_CHUNK_BOUNDARY")
        chunk=raw[i+8:i+8+size];actual=struct.unpack_from(">I",raw,i+8+size)[0]
        if zlib.crc32(kind+chunk)!=actual:raise ValueError("PILOT_PNG_CRC")
        i+=12+size;seen[kind]+=1
        if kind==b"IHDR":
            if seen[kind]!=1 or len(chunk)!=13 or struct.unpack_from(">II",chunk)!=(256,256):
                raise ValueError("PILOT_PNG_DIMENSIONS")
            if chunk[8:13]!=bytes([8,6,0,0,0]):
                raise ValueError("PILOT_PNG_RGBA_ONLY")
        if kind==b"IDAT":data.append(chunk)
        if kind==b"IEND":
            if len(chunk)!=0 or i!=len(raw):raise ValueError("PILOT_PNG_END")
            break
    if seen[b"IHDR"]!=1 or seen[b"IDAT"]<1 or seen[b"IEND"]!=1:
        raise ValueError("PILOT_PNG_REQUIRED_CHUNKS")
    stream=zlib.decompressobj()
    decoded=stream.decompress(b"".join(data), 270000)
    if not stream.eof or stream.unused_data or stream.unconsumed_tail or len(decoded)!=256*(1+256*4):
        raise ValueError("PILOT_PNG_IMAGE_BYTES")
    if any(decoded[x*1025]>4 for x in range(256)):
        raise ValueError("PILOT_PNG_SCANLINE_FILTER")
    return True

def svg_check(raw,concept):
    text=raw.decode("utf-8-sig")
    low=text.lower()
    forbidden=("<!doctype","<!entity","<script","<foreignobject","javascript:","xlink:","onload=",
               "onclick=","<image","<use","url(","@import","data:","<style")
    if any(x in low for x in forbidden):
        raise ValueError("PILOT_SVG_ACTIVE_CONTENT")
    try:root=ET.fromstring(text)
    except ET.ParseError as e:raise ValueError("PILOT_SVG_XML_INVALID") from e
    if root.tag!=SVG_NS+"svg" or root.get("viewBox")!="0 0 64 64":
        raise ValueError("PILOT_SVG_ROOT")
    tags=[node.tag.rsplit("}",1)[-1] for node in root.iter()]
    if set(tags)-SVG_TAGS:
        raise ValueError("PILOT_SVG_ELEMENT_FORBIDDEN")
    titles=[(node.text or "") for node in root.iter() if node.tag==SVG_NS+"title"]
    if len(titles)!=1 or concept.lower() not in titles[0].lower():
        raise ValueError("PILOT_SVG_ACCESSIBLE_TITLE")
    for node in root.iter():
        if any(name.lower().startswith("on") or "href" in name.lower()
               for name in node.attrib):
            raise ValueError("PILOT_SVG_UNSAFE_ATTRIBUTE")
    return True

class PreviewParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs=[]
        self.danger=[]
    def handle_starttag(self,tag,attrs):
        if tag in ("script","iframe","form","object","embed","base"):
            self.danger.append(tag)
        for key,val in attrs:
            if key in ("href","src"):
                self.refs.append(val)
            if key.startswith("on"):
                self.danger.append(key)

def verify(root):
    root=Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("PILOT_INVALID_PRIVATE_ROOT")
    source=root/"digital-products"/PRODUCT
    if source.is_symlink() or not source.is_dir():
        raise ValueError("PILOT_ORIGINAL_PRODUCT_MISSING")
    mpath=source/"manufacturing_manifest.json"
    manifest=read_json(mpath)
    archive=source/(PRODUCT+"-internal-qa.zip")
    if archive.is_symlink() or not archive.is_file() or not 100<archive.stat().st_size<=25*1024*1024:
        raise ValueError("PILOT_ORIGINAL_ZIP_MISSING")
    original=archive.read_bytes()
    family=manifest.get("family_id")
    src_sha=manifest.get("source_sha256")
    if (manifest.get("recipe")!=PRODUCT or family!="F34"
        or manifest.get("qa_status")!="passed" or not isinstance(src_sha,str)
        or not SHA.fullmatch(src_sha) or manifest.get("artifact_sha256")!=digest(original)
        or manifest.get("owner_publication_approval") is not False
        or manifest.get("public_listing_enabled") is not False):
        raise ValueError("PILOT_MANUFACTURING_SOURCE_CONTRACT_INVALID")
    qa=manifest.get("qa_measurements")
    if (not isinstance(qa,dict)
        or qa.get("review_kind")!="separate_automated_technical_verification"
        or qa.get("validated_archive_members")!=100
        or qa.get("archive_sha256")!=digest(original)
        or qa.get("critical_defects")!=[]
        or not isinstance(qa.get("gates"),dict)
        or len(qa["gates"])!=10
        or any(x is not True for x in qa["gates"].values())):
        raise ValueError("PILOT_ORIGINAL_TEN_TECHNICAL_GATES_MISSING")
    with zipfile.ZipFile(io.BytesIO(original)) as pack:
        infos=pack.infolist()
        files=[x.filename for x in infos]
        if len(files)!=100 or len(set(files))!=100 or pack.testzip() is not None:
            raise ValueError("PILOT_ORIGINAL_ZIP_INTEGRITY")
        for f in infos:
            if (f.is_dir() or f.flag_bits&1 or f.file_size>3*1024*1024
                or not f.filename.startswith(PRODUCT+"/")
                or any(p in ("",".","..") for p in f.filename.split("/"))
                or "\\" in f.filename or (f.external_attr>>16)&0o170000==0o120000):
                raise ValueError("PILOT_UNSAFE_ARCHIVE_MEMBER")
        names=set(x[len(PRODUCT)+1:] for x in files)
        if not DOCS.issubset(names):
            raise ValueError("PILOT_REQUIRED_DOCS_MISSING")
        catalog=json.loads(pack.read(PRODUCT+"/catalog.json"))
        icons=catalog.get("icons") if isinstance(catalog,dict) else None
        if not isinstance(icons,list) or len(icons)!=48:
            raise ValueError("PILOT_ICON_CATALOG_INVALID")
        expected=set(DOCS);ids=set()
        for item in icons:
            if not isinstance(item,dict):
                raise ValueError("PILOT_ICON_CATALOG_ITEM")
            ident=item.get("id")
            if not isinstance(ident,str) or not NAME.fullmatch(ident) or ident in ids:
                raise ValueError("PILOT_ICON_ID_DUPLICATE_OR_UNSAFE")
            if item.get("vector")!=ident+".svg" or item.get("raster")!=ident+".png":
                raise ValueError("PILOT_ICON_FILE_PAIR_MISMATCH")
            concept=item.get("concept")
            if not isinstance(concept,str) or not NAME.fullmatch(concept) or not ident.startswith(concept+"_"):
                raise ValueError("PILOT_ICON_CONCEPT_INVALID")
            svg_check(pack.read(PRODUCT+"/"+ident+".svg"),concept)
            png_check(pack.read(PRODUCT+"/"+ident+".png"))
            ids.add(ident);expected.add(ident+".svg");expected.add(ident+".png")
        if names!=expected:raise ValueError("PILOT_ARCHIVE_NOT_EXACTLY_48_PAIRS")
        readme=pack.read(PRODUCT+"/README.md").decode("utf-8")
        terms=pack.read(PRODUCT+"/LICENSE.txt").decode("utf-8")
        preview=pack.read(PRODUCT+"/preview.html").decode("utf-8")
        if len(readme)<400 or "PRIVATE internal QA artifact" not in terms:
            raise ValueError("PILOT_PROVENANCE_OR_TERMS_REVIEW_MISSING")
        view=PreviewParser();view.feed(preview)
        if view.danger or any(not isinstance(x,str) or x not in names for x in view.refs):
            raise ValueError("PILOT_PREVIEW_EXTERNAL_OR_BROKEN_LINK")
        if set(view.refs)!=expected-DOCS:
            raise ValueError("PILOT_PREVIEW_ASSET_REFERENCE_INCOMPLETE")
    mandate=root/"product-lifecycle/owner-commercial-instructions/20261020-commercial-direction.json"
    owner_in_principle=False
    if mandate.is_file() and not mandate.is_symlink():
        instruction=read_json(mandate)
        owner_in_principle=(
            instruction.get("schema")=="saeit.factory.owner-commercial-direction.v1"
            and instruction.get("in_principle_commercial_publication_authorized") is True
            and instruction.get("unreviewed_private_stock_publication_allowed") is False)
    return {
      "schema":"saeit.factory.f34-commercial-pilot-technical-gate.v1",
      "product_id":PRODUCT,"family_id":"F34",
      "source_sha256":src_sha,
      "original_zip_sha256":digest(original),
      "original_manifest_sha256":digest(mpath.read_bytes()),
      "automated_asset_integrity_verified":True,
      "original_ten_technical_gates_confirmed":True,
      "distinct_svg_png_pairs_verified":48,
      "all_100_archive_members_verified":True,
      "local_buyer_preview_links_verified":True,
      "owner_in_principle_direction_present":owner_in_principle,
      "original_source_zip_modified":False,
      "human_visual_or_specialist_acceptance_proven":False,
      "independent_license_and_asset_rights_signed":False,
      "price_tax_refund_and_license_offer_signed":False,
      "live_shop_release_gate_verified":False,
      "authenticated_buyer_checkout_and_entitlement_verified":False,
      "buyer_access_enabled":False,
      "commercial_publication_allowed":False,
      "sales_created":0,
      "remaining_commercial_blockers":BLOCKERS,
    }

def run(root):
    report=verify(root)
    original=Path(root)/"digital-products"/PRODUCT/(PRODUCT+"-internal-qa.zip")
    before=digest(original.read_bytes())
    dest=Path(root)/"product-lifecycle"/"commercial-pilot-readiness"
    if dest.is_symlink():raise ValueError("PILOT_OUTPUT_DIRECTORY_SYMLINK")
    dest.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(dest,0o700)
    payload=jsonbytes(report)
    filename=PRODUCT+"-"+report["original_zip_sha256"]+"-"+digest(payload)+".json"
    output=dest/filename
    if output.is_symlink():raise ValueError("PILOT_RECEIPT_SYMLINK")
    if output.exists():
        if output.read_bytes()!=payload:raise ValueError("PILOT_RECEIPT_IMMUTABILITY_FAILURE")
        status="existing_receipt_verified"
    else:
        fd,temp=tempfile.mkstemp(prefix=".pilot-",dir=str(dest))
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(payload);f.flush();os.fsync(f.fileno())
            os.chmod(temp,0o600)
            if output.exists():raise ValueError("PILOT_CONCURRENT_WRITE")
            os.replace(temp,output)
        finally:
            if os.path.exists(temp):os.unlink(temp)
        status="new_private_source_bound_receipt"
    if digest(original.read_bytes())!=before:raise RuntimeError("PILOT_ORIGINAL_CHANGED")
    if output.read_bytes()!=payload:raise RuntimeError("PILOT_READBACK_MISMATCH")
    return {"product_id":PRODUCT,"status":status,
            "receipt_sha256":digest(payload),
            "pairs_verified":report["distinct_svg_png_pairs_verified"],
            "member_count":100,
            "owner_direction_present":report["owner_in_principle_direction_present"],
            "commercial_blockers":len(BLOCKERS),
            "sale_enabled":False}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--factory-private-root",required=True)
    args=parser.parse_args()
    result=run(args.factory_private_root)
    print("REAL_F34_PILOT_COMMERCIAL_GATE="+json.dumps(result,sort_keys=True))
    print("REAL_F34_PILOT_NO_FALSE_COMMERCIAL_RELEASE=PASS")
