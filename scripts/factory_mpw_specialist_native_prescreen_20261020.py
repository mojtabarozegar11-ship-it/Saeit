#!/usr/bin/env python3
"""Real per-format private QA of MojPlayWin VPS factory stock and linked work orders.

Reads original hash-checked ZIPs. This is an engineering *prescreen*; media
playback, expert domain validity, usability, ownership, licenses and consent
are NOT implied. Outputs immutable, private source-bound evidence only.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import wave
import xml.etree.ElementTree as ET
import zipfile
import zlib

SCHEMA="saeit.factory.specialist-native-prescreen.v1"
EXPECTED={
    "F18":{".html",".js",".py",".json"},
    "F19":{".html",".css"},
    "F20":{".py",".json",".md"},
    "F21":{".py",".json",".md"},
    "F22":{".py",".json",".md"},
    "F25":{".csv",".json",".md"},
    "F27":{".xlsx",".ods"},
    "F28":{".py",".json",".md"},
    "F31":{".html",".svg"},
    "F34":{".svg",".png"},
    "F36":{".png",".exr"},
    "F37":{".gif",".mp4"},
    "F39":{".wav",".mp3"},
}
PAIRED={"F34":(".svg",".png",48),"F36":(".png",".exr",48),
        "F37":(".gif",".mp4",48),"F39":(".wav",".mp3",48)}
SHA=re.compile(r"^[0-9a-f]{64}$")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def html_gate(raw):
    class Markup(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.tags=Counter()
            self.external=[]
        def handle_starttag(self,tag,attrs):
            self.tags[tag]+=1
            for k,v in attrs:
                if (k in ("href","src") and isinstance(v,str) and
                        v.strip().lower().startswith(("http://","https://","//","javascript:"))):
                    self.external.append(k)
    # Broken markup is a specialist blocker, not a browser execution.
    text=raw.decode("utf-8-sig")
    parser=Markup()
    parser.feed(text)
    if parser.tags["html"]==0 or parser.tags["body"]==0 and parser.tags["main"]==0:
        raise ValueError("HTML_DOCUMENT_STRUCTURE_INCOMPLETE")
    if parser.external:
        raise ValueError("HTML_EXTERNAL_ASSET_OR_LINK_NEEDS_REVIEW")
    return "html_parser_and_external_reference_screen"


def png_gate(raw):
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("PNG_SIGNATURE")
    pos=8;chunks=Counter();size=None;payload=[]
    while pos<len(raw):
        if pos+12>len(raw):raise ValueError("PNG_TRUNCATED_CHUNK")
        length=struct.unpack_from(">I",raw,pos)[0];pos+=4
        name=raw[pos:pos+4];pos+=4
        if length>16_000_000 or pos+length+4>len(raw):
            raise ValueError("PNG_CHUNK_BOUNDARY")
        data=raw[pos:pos+length];pos+=length
        got=struct.unpack_from(">I",raw,pos)[0];pos+=4
        if got!=zlib.crc32(name+data):
            raise ValueError("PNG_CHUNK_CRC")
        chunks[name]+=1
        if name==b"IHDR":
            if len(data)!=13 or chunks[name]!=1:raise ValueError("PNG_IHDR")
            w,h=struct.unpack_from(">II",data)
            if not 1<=w<=8192 or not 1<=h<=8192:raise ValueError("PNG_DIMENSIONS")
            size=(w,h)
        elif name==b"IDAT":
            payload.append(data)
        elif name==b"IEND":
            if length!=0 or pos!=len(raw):raise ValueError("PNG_END")
            break
    if chunks[b"IEND"]!=1 or not size or not chunks[b"IDAT"]:
        raise ValueError("PNG_REQUIRED_CHUNKS")
    decomp=zlib.decompressobj()
    image_bytes=decomp.decompress(b"".join(payload), 60_000_000)
    if not decomp.eof or len(image_bytes)==0 or decomp.unconsumed_tail:
        raise ValueError("PNG_IMAGE_DATA_UNDECODABLE")
    return "png_all_chunk_crc_and_bounded_idat_inflate"


def mp4_gate(raw):
    seen=set();video=False;pos=0
    while pos+8<=len(raw):
        size=int.from_bytes(raw[pos:pos+4],"big")
        box=raw[pos+4:pos+8]
        offset=8
        if size==1:
            if pos+16>len(raw):raise ValueError("MP4_TRUNCATED_64BIT_BOX")
            size=int.from_bytes(raw[pos+8:pos+16],"big");offset=16
        elif size==0:size=len(raw)-pos
        if size<offset or pos+size>len(raw):
            raise ValueError("MP4_BOX_BOUNDARY")
        seen.add(box)
        if box==b"moov":
            video=b"vide" in raw[pos+offset:pos+size]
        pos+=size
    if pos!=len(raw) or not {b"ftyp",b"moov",b"mdat"}.issubset(seen) or not video:
        raise ValueError("MP4_VIDEO_TRACK_MISSING_OR_INVALID")
    return "mp4_atom_boundaries_and_video_track_header"


def wav_gate(raw):
    try:
        with wave.open(io.BytesIO(raw),"rb") as w:
            channels=w.getnchannels();rate=w.getframerate()
            frames=w.getnframes();sample=w.getsampwidth()
            if (w.getcomptype()!="NONE" or not 1<=channels<=2
                    or not 8000<=rate<=192000 or sample not in (1,2,3,4)
                    or frames<rate//5 or frames>rate*600):
                raise ValueError("WAV_CHANNEL_RATE_DURATION_INVALID")
            audio=w.readframes(min(frames,rate))
            if not audio or len(set(audio))<8:
                raise ValueError("WAV_SILENCE_OR_NO_PAYLOAD")
    except (wave.Error,EOFError) as e:
        raise ValueError("WAV_CONTAINER_UNREADABLE") from e
    return "wav_pcm_frames_rate_duration_and_nonzero_signal"


def mp3_gate(raw):
    start=0
    if raw.startswith(b"ID3") and len(raw)>=10:
        payload=raw[6:10]
        if any(x>=128 for x in payload):raise ValueError("MP3_ID3_SYNCHSAFE_INVALID")
        start=10+(payload[0]<<21)+(payload[1]<<14)+(payload[2]<<7)+payload[3]
    if start>=len(raw) or not any(
        raw[i]==255 and raw[i+1]&224==224 and raw[i+1]&24!=8
        for i in range(start,min(start+8192,len(raw)-1))):
        raise ValueError("MP3_MPEG_AUDIO_FRAME_NOT_FOUND")
    return "mp3_id3_and_mpeg_audio_frame_header"


def office_gate(blob,ext):
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as package:
            infos=package.infolist()
            if not 2<=len(infos)<=1500 or package.testzip() is not None:
                raise ValueError("OFFICE_ZIP_CRC_OR_MEMBERS")
            names={z.filename for z in infos}
            if any(".." in PurePosixPath(n).parts or n.startswith("/")
                   or n.lower().endswith((".vba",".bin",".exe")) for n in names):
                raise ValueError("OFFICE_MACRO_OR_UNSAFE_MEMBER")
            if ext==".xlsx":
                required={"[Content_Types].xml","xl/workbook.xml"}
                sheets=[n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml",n)]
                if not required.issubset(names) or not sheets:
                    raise ValueError("XLSX_WORKBOOK_SHEET_MISSING")
                targets=["xl/workbook.xml",sheets[0]]
            else:
                if "content.xml" not in names or "META-INF/manifest.xml" not in names:
                    raise ValueError("ODS_CONTENT_MANIFEST_MISSING")
                targets=["content.xml","META-INF/manifest.xml"]
            for name in targets:
                entry=package.getinfo(name)
                if entry.file_size>4_000_000:raise ValueError("OFFICE_XML_TOO_LARGE")
                root=ET.fromstring(package.read(name))
                if not list(root):raise ValueError("OFFICE_XML_EMPTY")
    except (zipfile.BadZipFile,ET.ParseError,KeyError) as e:
        raise ValueError("OFFICE_XML_OR_PACKAGE_INVALID") from e
    return "office_container_crc_required_sheets_and_xml_parse"


def check_one(ext,raw):
    if ext==".png":return png_gate(raw)
    if ext==".mp4":return mp4_gate(raw)
    if ext==".wav":return wav_gate(raw)
    if ext==".mp3":return mp3_gate(raw)
    if ext in (".xlsx",".ods"):return office_gate(raw,ext)
    if ext==".html":return html_gate(raw)
    if ext==".gif":
        if not (raw.startswith((b"GIF87a",b"GIF89a"))
                and raw.endswith(b";") and len(raw)>=40):
            raise ValueError("GIF_CONTAINER_INCOMPLETE")
        return "gif_signature_termination_only_no_frame_decode"
    if ext==".exr":
        if len(raw)<100 or raw[:4]!=b"\x76\x2f\x31\x01":
            raise ValueError("EXR_CONTAINER_INCOMPLETE")
        return "exr_magic_only_no_pixel_decode"
    return "courier_static_syntax_and_signature_prescreen"


def original_family_evidence(root,product,version,manifest,raw):
    """Recover a missing family only from the exact original QA receipt and bytes.

    Never infer from format, title, product name or another warehouse version.
    Original stock is immutable; this is a new source-bound evidence revision.
    """
    if root is None or manifest.get("family_id") is not None:
        return None
    directory=Path(root)/"digital-products"/product
    receipt=directory/"manufacturing_manifest.json"
    artifact=directory/(product+"-internal-qa.zip")
    if (directory.is_symlink() or not directory.is_dir()
            or not receipt.is_file() or receipt.is_symlink()
            or not artifact.is_file() or artifact.is_symlink()
            or not 0<receipt.stat().st_size<=65536
            or artifact.stat().st_size!=len(raw)):
        return None
    receipt_bytes=receipt.read_bytes()
    try:
        doc=json.loads(receipt_bytes)
    except (ValueError,UnicodeError):
        return None
    if (not isinstance(doc,dict)
            or doc.get("recipe")!=product
            or doc.get("source_sha256")!=version
            or doc.get("artifact_sha256")!=manifest.get("artifact_sha256")
            or doc.get("qa_status")!="passed"):
        return None
    family=doc.get("family_id")
    if family not in EXPECTED:
        return None
    digest=hashlib.sha256()
    with artifact.open("rb") as fp:
        for chunk in iter(lambda:fp.read(1024*1024),b""):
            digest.update(chunk)
    if digest.hexdigest()!=sha(raw):
        return None
    return family,sha(receipt_bytes)


def assess(product,version,manifest,raw,courier,source_root=None):
    # First party authenticated warehouse invariants precede every specialist
    # evaluation. No archive contents are executed, repaired, or published.
    courier.verify_stock(manifest,product,version,raw)
    blockers=[]
    tested=Counter();formats=Counter()
    try:
        courier.native_format_census(raw)
    except (RuntimeError,ValueError,KeyError,ET.ParseError,UnicodeError) as exc:
        blockers.append("ORIGINAL_NATIVE_STATIC_PRESCREEN_FAILED")
    fid=manifest.get("family_id")
    family_provenance_source="warehouse_manifest" if fid in EXPECTED else "not_verified"
    family_provenance_receipt_sha256=None
    if fid is None and source_root is not None:
        recovered=original_family_evidence(source_root,product,version,manifest,raw)
        if recovered:
            fid,family_provenance_receipt_sha256=recovered
            family_provenance_source="sha256_matched_original_manufacturing_qa"
    if fid not in EXPECTED:
        blockers.append("MISSING_OR_UNSUPPORTED_FAMILY_PROVENANCE")
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        names=package.namelist()
        if len(names)!=len(set(names)):
            blockers.append("DUPLICATE_ARCHIVE_MEMBER")
        stems=defaultdict(set)
        for info in package.infolist():
            if info.is_dir():continue
            ext=PurePosixPath(info.filename).suffix.lower()
            formats[ext]+=1
            stems[ext].add(PurePosixPath(info.filename).stem)
            try:
                check=check_one(ext,package.read(info.filename))
                tested[check]+=1
            except (ValueError,RuntimeError,UnicodeError,ET.ParseError,EOFError,
                    OSError,struct.error,zlib.error,zipfile.BadZipFile) as exc:
                blockers.append("FORMAT_CHECK_FAILED_"+ext.lstrip(".").upper())
        if fid in EXPECTED and not EXPECTED[fid].issubset(formats):
            blockers.append("FAMILY_REQUIRED_NATIVE_FORMAT_MISSING")
        if fid in PAIRED:
            a,b,needed=PAIRED[fid]
            if len(stems[a])!=needed or len(stems[b])!=needed or stems[a]!=stems[b]:
                blockers.append("FAMILY_SOURCE_PAIR_COUNT_OR_NAMES_INVALID")
    # Both static tests and real media-container parsing remain narrower than
    # independent user functionality tests and qualified expert assessment.
    return {
        "schema":SCHEMA,"tenant":courier.TENANT,
        "product_id":product,"source_sha256":version,
        "original_factory_artifact_sha256":sha(raw),
        "family_id":fid if isinstance(fid,str) and fid in EXPECTED else None,
        "family_provenance_source":family_provenance_source,
        "family_provenance_receipt_sha256":family_provenance_receipt_sha256,
        "source_integrity_verified":True,
        "static_and_container_checks_applied":dict(sorted(tested.items())),
        "format_counts":dict(sorted(formats.items())),
        "automated_format_prescreen_passed":not bool(blockers),
        "automated_technical_blockers":sorted(set(blockers)),
        "media_full_decode_verified":False,
        "python_or_javascript_executed":False,
        "functional_acceptance_for_native_product_verified":False,
        "qualified_specialist_content_review_passed":False,
        "verified_asset_ownership_and_licenses":False,
        "owner_sale_and_publication_permission":False,
        "commercial_release":False,
        "store_listing_allowed":False,
        "final_work_order_completed":False,
        "recommended_next_step":(
            "repair_native_format_or_family_provenance_and_rerun_prescreen"
            if blockers else "perform_independent_runtime_domain_rights_and_owner_review")
    }


def run(root,courier,engine_path=None):
    root=Path(root)
    courier.clean_dir(root)
    results={}
    counters=Counter()
    stage=root/"design-state"
    courier.private_new(stage)
    dest=stage/"mojplaywin-native-specialist-evidence"
    courier.private_new(dest)
    for product,version,manifest,raw in courier.stock_records(root):
        report=assess(product,version,manifest,raw,courier,root)
        fingerprint=sha(courier.json_blob(report))
        sub=dest/product
        courier.private_new(sub)
        target=sub/(version+"-"+fingerprint+".json")
        payload=courier.json_blob(report)
        if target.exists():
            if target.is_symlink() or target.read_bytes()!=payload:
                raise RuntimeError("SPECIALIST_IMMUTABLE_EVIDENCE_CONFLICT")
        else:
            courier.atomic(target,payload)
        results[(product,version)]=(fingerprint,report)
        counters["original_stock_checked"]+=1
        if report["family_provenance_source"]=="sha256_matched_original_manufacturing_qa":
            counters["source_sha_matched_family_recoveries"]+=1
        counters["prescreen_format_passed" if report["automated_format_prescreen_passed"]
                 else "prescreen_format_blocked"]+=1
        for issue in report["automated_technical_blockers"]:
            counters["blocker_"+issue]+=1
    engine=courier._native_order_engine(engine_path)
    orders=root/"production-instructions/orders"
    courier.clean_dir(orders)
    wos=root/"production-instructions/mojplaywin-specialist-order-reports"
    courier.private_new(wos)
    for p in sorted(orders.iterdir()):
        if p.is_symlink() or not p.is_file() or not engine.ORDER_RE.fullmatch(p.name):
            raise RuntimeError("SPECIALIST_UNSAFE_CANONICAL_WORK_ORDER")
        row=engine.validate_old(p)
        if row.get("requesting_site")!="mojplaywin.com":continue
        counters["site_origin_work_orders_examined"]+=1
        entry=results.get((row.get("source_product_id"),row.get("source_sha256")))
        if entry is None:
            counters["site_origin_work_orders_missing_source"]+=1
            continue
        fingerprint,report=entry
        packet={
            "schema":"saeit.factory.specialist-work-order-dossier.v1",
            "work_order":row["id"],
            "source_work_order_sha256":sha(p.read_bytes()),
            "specialist_prescreen_sha256":fingerprint,
            "original_source_sha256":row["source_sha256"],
            "source_artifact_sha256":row["source_artifact_sha256"],
            "family_id":report["family_id"],
            "current_order_status":row["status"],
            "format_prescreen_passed":report["automated_format_prescreen_passed"],
            "current_engineering_defects":report["automated_technical_blockers"],
            "needs_independent_functional_review":True,
            "needs_domain_and_scientific_review":True,
            "needs_licensing_and_rights_review":True,
            "needs_owner_commercial_approval":True,
            "engineering_work_order_completed":False,
            "commercial_approval":False}
        if packet["source_artifact_sha256"]!=report["original_factory_artifact_sha256"]:
            raise RuntimeError("SPECIALIST_WORK_ORDER_ORIGINAL_SOURCE_MISMATCH")
        version=sha(courier.json_blob(packet))
        target=wos/(row["id"]+"-"+version+".json")
        if target.exists():
            if target.is_symlink() or target.read_bytes()!=courier.json_blob(packet):
                raise RuntimeError("SPECIALIST_ORDER_PACKET_IMMUTABILITY")
        else:
            courier.atomic(target,courier.json_blob(packet))
        counters["site_origin_work_orders_evidence_linked"]+=1
    summary={"schema":SCHEMA,"tenant":courier.TENANT,
             "counts":dict(sorted(counters.items())),
             "commercial_approval_count":0,
             "product_publications":0,
             "completed_manufacturing_work_orders_claimed":0,
             "original_warehouse_goods_mutated":False,
             "expert_reviews_pending":len(results),
             "evidence_kind":"original_zip_static_and_binary_container_check_only"}
    courier.atomic(dest/"dashboard.json",courier.json_blob(summary))
    return summary


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--factory-private-root",required=True)
    ap.add_argument("--engine-path",default=None)
    args=ap.parse_args()
    import mpw_vps_warehouse_courier as courier
    out=run(args.factory_private_root,courier,args.engine_path)
    print("MPW_VPS_SPECIALIST_NATIVE_PRESCREEN="+json.dumps(out,sort_keys=True))
    print("MPW_VPS_SPECIALIST_NO_AUTO_COMMERCIAL_RELEASE=PASS")


if __name__=="__main__":
    main()
