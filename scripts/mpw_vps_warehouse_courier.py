#!/usr/bin/env python3
"""One MojPlayWin-only VPS warehouse courier and QA return robot.

The VPS is the authority for product bytes. The cPanel recipient is a PRIVATE
QA inbox, never a public shop. All failed/incomplete downstream quality
reviews are routed as immutable stage-one factory rework requests. A return
is a corrective *request*, not evidence that a factory editor executed it.
CLI modes run through the GitHub Actions SSH bastion; no new APIs or secrets.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import ast
import csv
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import zipfile
import xml.etree.ElementTree as ET

TENANT = "mojplaywin-main"
SCHEMA = "mpw.factory.warehouse-courier.v1"
RETURN_SCHEMA = "mpw.factory.return-to-stage1.v1"
NATIVE_PREVIEW_SCHEMA = "saeit.factory.native-source-review-package.v1"
VPS = Path.home() / "factory-runtime/private/autonomous-product-cycle"
PANEL = Path("/home/zomorod2/.private_mojplaywin_main_agents")
DEST = PANEL / "evolution_runtime_20261018/warehouse_courier"
RECIPE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
MAX_ZIP = 25 * 1024 * 1024
MAX_PACKAGE = 110 * 1024 * 1024
MAX_ITEMS = 50
MAX_FILES = 201
MAX_UNCOMPRESSED = 80 * 1024 * 1024
ISSUES = (
    "INDEPENDENT_CONTENT_QUALITY_REVIEW_REQUIRED",
    "OWNERSHIP_AND_ASSET_LICENSE_REVIEW_REQUIRED",
    "COMMERCIAL_PUBLICATION_APPROVAL_REQUIRED",
)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def clean_dir(path):
    require(path.is_dir() and not path.is_symlink(), "UNSAFE_OR_MISSING_PRIVATE_DIRECTORY")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def private_new(path):
    require(not path.is_symlink(), "PRIVATE_SYMLINK_REJECTED")
    if not path.exists():
        path.mkdir(mode=0o700)
    clean_dir(path)
    require(path.stat().st_mode & 0o077 == 0, "PRIVATE_DIRECTORY_PERMISSIONS")


def atomic(path, raw):
    require(not path.is_symlink(), "OUTPUT_SYMLINK_REFUSED")
    fd, name = tempfile.mkstemp(prefix=".mpw-courier-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.lexists(name):
            os.unlink(name)


def json_blob(obj):
    raw = (json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf8")
    require(len(raw) < 1_000_000, "JSON_REPORT_TOO_LARGE")
    return raw


def json_file(path, max_size=1_000_000):
    require(path.is_file() and not path.is_symlink()
            and 0 < path.stat().st_size <= max_size, "INVALID_JSON_SOURCE")
    obj = json.loads(path.read_bytes())
    require(isinstance(obj, dict), "INVALID_JSON_OBJECT")
    return obj


def safe_zip(raw):
    require(0 < len(raw) <= MAX_ZIP, "ZIP_SIZE_REJECTED")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = set()
            uncompressed = 0
            infos = z.infolist()
            require(0 < len(infos) <= 300, "ZIP_ENTRY_LIMIT")
            for entry in infos:
                name = entry.filename
                parts = PurePosixPath(name).parts
                require(name and "\\" not in name and not name.startswith("/")
                        and not any(x in ("..", ".") for x in parts)
                        and name not in names, "ZIP_TRAVERSAL_OR_DUPLICATE")
                names.add(name)
                mode = (entry.external_attr >> 16) & 0o170000
                require(mode != 0o120000 and not entry.flag_bits & 1, "ZIP_LINK_OR_ENCRYPTION")
                uncompressed += entry.file_size
                require(entry.file_size >= 0 and uncompressed <= MAX_UNCOMPRESSED,
                        "ZIP_UNPACKED_SIZE_LIMIT")
                require(entry.file_size <= max(entry.compress_size, 1) * 120
                        or entry.file_size <= 1024 * 1024, "ZIP_EXPANSION_RATIO")
            require(z.testzip() is None, "ZIP_CRC_FAILED")
    except (zipfile.BadZipFile, OSError, ValueError) as err:
        raise RuntimeError("INVALID_PRODUCT_ZIP") from err


def verify_stock(manifest, recipe, version, raw):
    require(bool(RECIPE.fullmatch(recipe)) and bool(SHA.fullmatch(version)), "UNSAFE_PRODUCT_ID")
    require(manifest.get("schema") == "saeit.factory.production-warehouse.v1"
            and manifest.get("product_id") == recipe
            and manifest.get("source_sha256") == version
            and manifest.get("manufacturing_qc") == "passed"
            and manifest.get("production_state") == "finished_goods_in_factory"
            and manifest.get("commercial_release") is False
            and manifest.get("site_transfer_state") == "not_transferred"
            and manifest.get("content_rights_market_review") == "pending"
            and manifest.get("receiving_site") is None
            and manifest.get("bytes") == len(raw)
            and manifest.get("artifact_sha256") == digest(raw), "WAREHOUSE_RECEIPT_NOT_VERIFIED")
    safe_zip(raw)
    return True


def native_format_census(raw):
    """Independent *static* checks of real source members; not software execution or rights approval.

    Each member must be a recognized document, code source or media format. ZIP
    integrity/traversal/symlink/size protections are always checked first.
    """
    safe_zip(raw)
    formats = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        require(0 < len(members) <= 300, "NATIVE_EMPTY_OR_OVERSIZED_SOURCE")
        for info in members:
            require(not info.is_dir(), "NATIVE_DIRECTORY_MEMBER_UNEXPECTED")
            suffix = PurePosixPath(info.filename).suffix.lower()
            require(suffix in {".py", ".json", ".md", ".txt", ".html", ".css",
                               ".js", ".svg", ".png", ".xlsx", ".ods", ".csv",
                               ".gif", ".mp4", ".exr", ".wav", ".mp3", ".pdf",
                               ".docx", ".epub"}, "NATIVE_SPECIALIST_FORMAT_UNSUPPORTED")
            check_as_text = suffix in {".py",".json",".md",".txt",".html",".css",".js",".svg",".csv"}
            limit = 2_000_001 if check_as_text else 16384
            with archive.open(info) as fp:
                head = fp.read(min(info.file_size, limit))
            require(bool(head), "NATIVE_EMPTY_DELIVERABLE")
            if check_as_text:
                require(info.file_size <= 2_000_000, "NATIVE_TEXT_TOO_LARGE_FOR_STATIC_QA")
                try:
                    decoded = head.decode("utf-8-sig")
                except UnicodeError as exc:
                    raise RuntimeError("NATIVE_TEXT_ENCODING_UNVERIFIED") from exc
                require(bool(decoded.strip()), "NATIVE_EMPTY_TEXT")
                if suffix == ".json":
                    json.loads(decoded)
                elif suffix == ".py":
                    ast.parse(decoded, filename="<factory-native-static-check>")
                elif suffix == ".svg":
                    try:
                        svg = ET.fromstring(decoded)
                    except ET.ParseError as exc:
                        raise RuntimeError("NATIVE_SVG_XML_INVALID") from exc
                    require(svg.tag.split("}")[-1].lower() == "svg", "NATIVE_SVG_NOT_SVG")
                    for element in svg.iter():
                        require(element.tag.split("}")[-1].lower() not in ("script","foreignobject"),
                                "NATIVE_UNSAFE_SVG_ELEMENT")
                        for k,v in element.attrib.items():
                            name=k.split("}")[-1].lower()
                            require(not name.startswith("on"), "NATIVE_SVG_EVENT_HANDLER")
                            if name == "href":
                                require(not v.strip().lower().startswith(("http:","https:","javascript:","data:")),
                                        "NATIVE_SVG_EXTERNAL_REFERENCE")
                elif suffix == ".html":
                    require("<html" in decoded.lower() or "<!doctype" in decoded.lower(),
                            "NATIVE_HTML_DOCUMENT_UNVERIFIED")
                elif suffix == ".csv":
                    require(len(list(csv.reader(io.StringIO(decoded)))) >= 1, "NATIVE_CSV_EMPTY")
            else:
                if suffix == ".png":
                    require(head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR"
                            and 0 < int.from_bytes(head[16:20], "big") <= 32768
                            and 0 < int.from_bytes(head[20:24], "big") <= 32768,
                            "NATIVE_PNG_SIGNATURE_OR_DIMENSION")
                elif suffix == ".gif":
                    require(head[:6] in (b"GIF87a",b"GIF89a"), "NATIVE_GIF_SIGNATURE")
                elif suffix == ".mp4":
                    require(head[4:8] == b"ftyp", "NATIVE_MP4_SIGNATURE")
                elif suffix == ".exr":
                    require(head[:4] == b"\x76\x2f\x31\x01", "NATIVE_EXR_SIGNATURE")
                elif suffix == ".wav":
                    require(head[:4] == b"RIFF" and head[8:12] == b"WAVE",
                            "NATIVE_WAV_SIGNATURE")
                elif suffix == ".mp3":
                    require(head[:3] == b"ID3" or (len(head)>=2 and head[0]==255 and (head[1]&224)==224),
                            "NATIVE_MP3_SIGNATURE")
                elif suffix == ".pdf":
                    require(head.startswith(b"%PDF-"), "NATIVE_PDF_SIGNATURE")
                elif suffix in (".xlsx",".ods",".docx",".epub"):
                    require(head.startswith(b"PK"), "NATIVE_OFFICE_CONTAINER_SIGNATURE")
            formats[suffix]=formats.get(suffix,0)+1
    require(any(ext in formats for ext in (".py",".csv",".xlsx",".ods",".html",
            ".svg",".png",".gif",".mp4",".exr",".wav",".mp3",".pdf",".docx",".epub")),
            "NATIVE_NO_REAL_DELIVERABLES")
    return {"inspected_members":len(members),"format_counts":dict(sorted(formats.items())),
            "scope":"static file syntax, signatures, archive safety and source integrity only",
            "code_execution_verified":False, "domain_quality_verified":False}


def verify_native_private_preview(report, raw, product, version, original_sha):
    """Validate native review-package provenance; it never becomes a sale-ready bundle."""
    require(isinstance(report,dict)
            and report.get("schema")==NATIVE_PREVIEW_SCHEMA
            and report.get("product_id")==product
            and report.get("factory_source_sha256")==version
            and report.get("factory_internal_zip_sha256")==original_sha
            and report.get("native_structural_review_passed") is True
            and report.get("technical_buyer_package_verified") is False
            and report.get("consumer_cli_smoke_examples_passed")==0
            and report.get("independent_domain_review_completed") is False
            and report.get("rights_and_license_review_completed") is False
            and report.get("eligible_for_commercial_listing") is False
            and report.get("commercial_release") is False
            and report.get("public_download_allowed") is False
            and report.get("price") is None
            and report.get("package_bytes")==len(raw)
            and report.get("package_sha256")==digest(raw),
            "NATIVE_PREVIEW_APPROVAL_OR_IDENTITY_INVALID")
    safe_zip(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        needed={"product/ORIGINAL_FACTORY_PRODUCT.zip","guide/START_HERE.md",
                "qa/NATIVE_STRUCTURE_QA.json","qa/SHA256SUMS.txt",
                "license/REVIEW_REQUIRED.txt"}
        require(set(package.namelist()) == needed, "NATIVE_PREVIEW_MEMBER_LIST_INVALID")
        original = package.read("product/ORIGINAL_FACTORY_PRODUCT.zip")
        require(digest(original)==original_sha, "NATIVE_PREVIEW_SOURCE_HASH_DRIFT")
        require(b"NOT LICENSED FOR PUBLIC RESALE" in package.read("license/REVIEW_REQUIRED.txt"),
                "NATIVE_PREVIEW_NO_LICENSE_HOLD")
        report_qa=json.loads(package.read("qa/NATIVE_STRUCTURE_QA.json"))
        require(report_qa.get("original_artifact_sha256")==original_sha
                and report_qa.get("original_source_sha256")==version
                and report_qa.get("native_formats")==native_format_census(original)
                and report_qa.get("human_expert_reviewed") is False
                and report_qa.get("commercial_release") is False,
                "NATIVE_PREVIEW_FORMAT_EVIDENCE_INVALID")
        lines=package.read("qa/SHA256SUMS.txt").decode("utf8").splitlines()
        require(len(lines)==4, "NATIVE_PREVIEW_HASH_LIST")
        for line in lines:
            sha,sep,name=line.partition("  ")
            require(bool(sep) and bool(SHA.fullmatch(sha)) and name in needed
                    and name!="qa/SHA256SUMS.txt" and digest(package.read(name))==sha,
                    "NATIVE_PREVIEW_MEMBER_HASH_MISMATCH")
    return True


def customer_companion(root, product, version, original_sha):
    """Only a source-bound *private* buyer bundle; never a store-sale approval."""
    candidate = Path(root) / "customer-packs" / product / version
    if candidate.is_symlink():
        raise RuntimeError("CUSTOMER_CANDIDATE_SYMLINK")
    if not candidate.exists():
        return None
    clean_dir(candidate)
    manifest_path = candidate / "candidate_manifest.json"
    archive_path = candidate / "customer-package.zip"
    report = json_file(manifest_path, 100_000)
    require(archive_path.is_file() and not archive_path.is_symlink()
            and 0 < archive_path.stat().st_size <= MAX_ZIP, "CUSTOMER_PACKAGE_FILE_INVALID")
    raw = archive_path.read_bytes()
    validate_customer_companion(report, raw, product, version, original_sha)
    return report, raw


def validate_customer_companion(report, raw, product, version, original_sha):
    if isinstance(report,dict) and report.get('schema')==NATIVE_PREVIEW_SCHEMA:
        return verify_native_private_preview(report,raw,product,version,original_sha)
    require(isinstance(report, dict)
            and report.get("schema") == "saeit.factory.consumer-package.v1"
            and report.get("product_id") == product
            and report.get("factory_source_sha256") == version
            and report.get("factory_internal_zip_sha256") == original_sha
            and report.get("technical_buyer_package_verified") is True
            and report.get("consumer_cli_smoke_examples_passed") == 2
            and report.get("independent_domain_review_completed") is False
            and report.get("rights_and_license_review_completed") is False
            and report.get("eligible_for_commercial_listing") is False
            and report.get("commercial_release") is False
            and report.get("public_download_allowed") is False
            and report.get("price") is None
            and report.get("package_bytes") == len(raw)
            and report.get("package_sha256") == digest(raw),
            "CUSTOMER_PACKAGE_SHA_OR_RELEASE_GATE_INVALID")
    safe_zip(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        needed={"product/calculator.py","product/example_inputs.json",
                "guide/START_HERE.md","qa/SHA256SUMS.txt",
                "license/REVIEW_REQUIRED.txt"}
        require(needed.issubset(set(package.namelist())),
                "CUSTOMER_PACKAGE_DELIVERABLES_MISSING")
        require(b"NOT LICENSED FOR PUBLIC RESALE" in package.read("license/REVIEW_REQUIRED.txt"),
                "CUSTOMER_PACKAGE_LICENSE_HOLD_MISSING")
        sums=package.read("qa/SHA256SUMS.txt").decode("utf8")
        for line in sums.splitlines():
            sha, sep, name=line.partition("  ")
            require(sep and SHA.fullmatch(sha) and name in package.namelist()
                    and digest(package.read(name))==sha,
                    "CUSTOMER_PACKAGE_MEMBER_DIGEST_FAILED")
    return True


def stock_records(root):
    """Return one bounded, rotating page of authenticated warehouse stock.

    The hourly courier can inspect a warehouse larger than MAX_ITEMS without
    unbounded memory or archive growth. Rotation is stable within the UTC hour,
    so retries export the same page; later scheduled runs advance through all
    pages. Every selected record is still fully hash-verified before transfer.
    """
    clean_dir(root)
    finished = root / "production-warehouse/finished"
    clean_dir(finished)
    identities = []
    for product in sorted(finished.iterdir()):
        require(not product.is_symlink() and product.is_dir()
                and RECIPE.fullmatch(product.name), "WAREHOUSE_PRODUCT_PATH_INVALID")
        for version in sorted(product.iterdir()):
            require(not version.is_symlink() and version.is_dir()
                    and SHA.fullmatch(version.name), "WAREHOUSE_VERSION_PATH_INVALID")
            identities.append((product, version))
    if not identities:
        return []
    page_count = (len(identities) + MAX_ITEMS - 1) // MAX_ITEMS
    utc_hour = int(datetime.now(timezone.utc).timestamp() // 3600)
    page = utc_hour % page_count
    start = page * MAX_ITEMS
    selected = identities[start:start + MAX_ITEMS]
    print("MPW_WAREHOUSE_PAGE=" + str(page) + "/" + str(page_count),
          file=sys.stderr, flush=True)
    result = []
    for product, version in selected:
        manifest_path = version / "warehouse_manifest.json"
        artifact_path = version / "product.zip"
        manifest = json_file(manifest_path, 100_000)
        require(artifact_path.is_file() and not artifact_path.is_symlink()
                and artifact_path.stat().st_size <= MAX_ZIP, "WAREHOUSE_ZIP_INVALID")
        raw = artifact_path.read_bytes()
        verify_stock(manifest, product.name, version.name, raw)
        result.append((product.name, version.name, manifest, raw))
    return result

def add_tar(tar, name, raw):
    require(len(raw) <= MAX_ZIP, "ARCHIVE_MEMBER_TOO_LARGE")
    info = tarfile.TarInfo(name)
    info.size = len(raw)
    info.mode = 0o600
    info.mtime = 0
    tar.addfile(info, io.BytesIO(raw))


def export_factory(root=VPS, page=None):
    # Status to stderr only: stdout is the authenticated binary archive stream.
    print("MPW_VPS_EXPORT_BEGIN=PASS", file=sys.stderr, flush=True)
    records = stock_records(Path(root))
    print("MPW_VPS_EXPORT_STOCK_VERIFIED="+str(len(records)), file=sys.stderr, flush=True)
    companions = {(p,v):customer_companion(root,p,v,m["artifact_sha256"])
                  for p,v,m,raw in records}
    # Three buyer-format goods per courier cycle; retain every underlying
    # original stock record so the Stage-1 QA feedback contract is unchanged.
    eligible=sorted(k for k,v in companions.items() if v is not None)
    if page is not None:
        require(type(page) is int and 0<=page<=16,"WAREHOUSE_PRIVATE_BATCH_PAGE_INVALID")
        selected=set(eligible[page*3:page*3+3])
        companions={key:(value if key in selected else None)
                    for key,value in companions.items()}
        print("MPW_NATIVE_BATCH_PAGE="+str(page)+
              " SELECTED="+str(len(selected)), file=sys.stderr, flush=True)
    elif len(eligible)>3:
        now=datetime.now(timezone.utc)
        pointer=((now.date().toordinal()*24+now.hour)*3)%len(eligible)
        selected={eligible[(pointer+i)%len(eligible)] for i in range(3)}
        companions={key:(value if key in selected else None)
                    for key,value in companions.items()}
    stream = io.BytesIO()
    # Stored products are already ZIP-compressed; gzip level 1 avoids expensive
    # recompression on the low-CPU VPS without relaxing any archive/QA checks.
    with tarfile.open(fileobj=stream, mode="w:gz", compresslevel=1) as tar:
        index = {"schema": SCHEMA, "tenant": TENANT, "created_utc": stamp(),
                 "inventory_count": len(records),
                 "items": [{"product_id":p, "version":v,
                            "artifact_sha256":m["artifact_sha256"],
                            "bytes":len(blob),
                            "consumer_package_sha256":(
                                companions[(p,v)][0]["package_sha256"]
                                if companions[(p,v)] is not None else None)}
                           for p,v,m,blob in records]}
        add_tar(tar, "index.json", json_blob(index))
        for product, version, manifest, raw in records:
            name = "items/" + product + "/" + version + "/"
            add_tar(tar, name + "manifest.json", json_blob(manifest))
            add_tar(tar, name + "product.zip", raw)
            if companions[(product,version)] is not None:
                customer_manifest,customer_bytes=companions[(product,version)]
                add_tar(tar, name + "customer_manifest.json", json_blob(customer_manifest))
                add_tar(tar, name + "customer-package.zip", customer_bytes)
    value = stream.getvalue()
    require(len(value) <= MAX_PACKAGE, "WAREHOUSE_TRANSFER_TOO_LARGE")
    print("MPW_VPS_EXPORT_TRANSFER_BYTES="+str(len(value)), file=sys.stderr, flush=True)
    return value


def unpack(raw):
    require(0 < len(raw) <= MAX_PACKAGE, "BAD_WAREHOUSE_BATCH")
    try:
        archive = tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz")
    except tarfile.TarError as error:
        raise RuntimeError("UNTRUSTED_TRANSFER_ARCHIVE") from error
    with archive:
        members = archive.getmembers()
        require(1 <= len(members) <= MAX_FILES
                and all(m.isfile() and not m.issym() and not m.islnk()
                        and 0 <= m.size <= MAX_ZIP for m in members),
                "UNEXPECTED_TRANSFER_MEMBER")
        names = [x.name for x in members]
        require(len(set(names)) == len(names) and "index.json" in names,
                "DUPLICATE_TRANSFER_ENTRY")
        blobs = {item.name: archive.extractfile(item).read() for item in members}
    index = json.loads(blobs["index.json"])
    require(index.get("schema") == SCHEMA and index.get("tenant") == TENANT
            and isinstance(index.get("items"), list)
            and len(index["items"]) <= MAX_ITEMS
            and index.get("inventory_count") == len(index["items"]), "INVALID_BATCH_INDEX")
    expected = {"index.json"}
    products = []
    seen = set()
    for item in index["items"]:
        require(isinstance(item, dict), "BAD_BATCH_ROW")
        product, version = item.get("product_id"), item.get("version")
        require(isinstance(product, str) and RECIPE.fullmatch(product)
                and isinstance(version, str) and SHA.fullmatch(version)
                and (product, version) not in seen, "BAD_OR_DUPLICATE_PRODUCT_ROW")
        seen.add((product, version))
        base = "items/" + product + "/" + version + "/"
        expected.update((base + "manifest.json", base + "product.zip"))
        require(item.get("artifact_sha256") == digest(blobs.get(base+"product.zip",b""))
                and item.get("bytes") == len(blobs.get(base+"product.zip",b"")),
                "BATCH_HASH_OR_SIZE_INVALID")
        manifest = json.loads(blobs[base + "manifest.json"])
        verify_stock(manifest, product, version, blobs[base+"product.zip"])
        customer=None
        candidate_sha=item.get("consumer_package_sha256")
        if candidate_sha is not None:
            require(isinstance(candidate_sha,str) and SHA.fullmatch(candidate_sha),
                    "CUSTOMER_BATCH_SHA_INVALID")
            expected.update((base+"customer_manifest.json",base+"customer-package.zip"))
            require(base+"customer_manifest.json" in blobs
                    and base+"customer-package.zip" in blobs,
                    "CUSTOMER_BATCH_FILE_MISSING")
            report=json.loads(blobs[base+"customer_manifest.json"])
            raw_customer=blobs[base+"customer-package.zip"]
            require(report.get("package_sha256")==candidate_sha,
                    "CUSTOMER_BATCH_MANIFEST_MISMATCH")
            validate_customer_companion(report,raw_customer,product,version,
                                        manifest["artifact_sha256"])
            customer=(report,raw_customer)
        products.append((product, version, manifest, blobs[base+"product.zip"],customer))
    require(set(blobs) == expected, "UNEXPECTED_TRANSFER_PATH")
    return products


def target_root(root):
    root = Path(root)
    if not root.exists():
        clean_dir(root.parent)
        require(root.parent.stat().st_mode & 0o077 == 0, "MPW_RECIPIENT_PARENT_NOT_PRIVATE")
        root.mkdir(mode=0o700)
    clean_dir(root)
    require(root.stat().st_mode & 0o077 == 0, "MPW_RECIPIENT_NOT_PRIVATE")
    return root


def import_site(batch, root=DEST):
    products = unpack(batch)
    root = target_root(root)
    private_new(root / "received")
    private_new(root / "returns")
    added, previous = 0, 0
    customer_added,customer_existing,customer_missing=0,0,0
    native_preview_added=native_preview_existing=0
    rows = []
    for product, version, manifest, content, customer in products:
        parent = root/"received"/product
        private_new(parent)
        version_dir = parent / version
        if version_dir.exists() or version_dir.is_symlink():
            clean_dir(version_dir)
            old = json_file(version_dir/"warehouse_manifest.json",100_000)
            oldbytes = (version_dir/"product.zip").read_bytes()
            verify_stock(old,product,version,oldbytes)
            require(digest(oldbytes) == digest(content), "CHANGED_RECEIVED_VERSION")
            previous += 1
        else:
            version_dir.mkdir(mode=0o700)
            atomic(version_dir/"product.zip",content)
            atomic(version_dir/"warehouse_manifest.json",json_blob(manifest))
            added += 1
        # A deliberately sparse page transports at most 3 preview bundles.
        # All other private, previously received companions MUST be reverified
        # locally instead of getting their site QA status downgraded to "missing".
        if customer is None:
            old_manifest=version_dir/"customer_manifest.json"
            old_zip=version_dir/"customer-package.zip"
            if old_manifest.exists() or old_zip.exists():
                require(old_manifest.is_file() and not old_manifest.is_symlink()
                        and old_zip.is_file() and not old_zip.is_symlink(),
                        "CUSTOMER_PRIVATE_PREVIOUS_PARTIAL_OR_UNSAFE")
                old_report=json_file(old_manifest,100_000)
                old_raw=old_zip.read_bytes()
                validate_customer_companion(old_report,old_raw,product,version,
                                            manifest["artifact_sha256"])
                customer=(old_report,old_raw)
        native_preview=(customer is not None and customer[0].get("schema")==NATIVE_PREVIEW_SCHEMA)
        if customer is not None:
            candidate_report,candidate_zip=customer
            candidate_zip_path=version_dir/"customer-package.zip"
            candidate_manifest_path=version_dir/"customer_manifest.json"
            if candidate_zip_path.exists() or candidate_manifest_path.exists():
                require(candidate_zip_path.is_file() and not candidate_zip_path.is_symlink()
                        and candidate_manifest_path.is_file() and not candidate_manifest_path.is_symlink()
                        and digest(candidate_zip_path.read_bytes())==candidate_report["package_sha256"]
                        and json_file(candidate_manifest_path)==candidate_report,
                        "CUSTOMER_PREVIOUS_RECEIPT_CONFLICT")
                if native_preview:native_preview_existing+=1
                else:customer_existing+=1
            else:
                atomic(candidate_zip_path,candidate_zip)
                atomic(candidate_manifest_path,json_blob(candidate_report))
                if native_preview:native_preview_added+=1
                else:customer_added+=1
        if customer is None or native_preview:
            customer_missing+=1
        # This independent QA does NOT invent a content, licensing or owner
        # approval. Missing commercial verification returns to stage one.
        issues = list(ISSUES)
        qa = {"schema": SCHEMA,"tenant":TENANT,"product_id":product,
              "version":version,"artifact_sha256":manifest["artifact_sha256"],
              "technical_zip_verified":True,
              "customer_bundle_verified":customer is not None and not native_preview,
              "native_private_structure_preview_verified":bool(native_preview),
              "customer_package_sha256":(customer[0]["package_sha256"] if customer else None),
              "commercial_approved":False,
              "qa_state":"requires_factory_stage1_rework","issue_codes":issues,
              "public_listing":False,"payment_enabled":False,
              "preserve_original":True}
        atomic(version_dir/"site_qa.json",json_blob(qa))
        folder = root/"returns"/product
        private_new(folder)
        ret = {"schema":RETURN_SCHEMA,"tenant":TENANT,"product_id":product,
               "source_sha256":version,"artifact_sha256":manifest["artifact_sha256"],
               "stage":1,"status":"return_for_qa_completion",
               "issues":issues,"correction_required":
                 "Re-enter first factory design and review stage; obtain actual independent content, rights and owner release evidence. Repeat QA before website publication.",
               "published":False,"factory_original_must_be_preserved":True}
        # Preserve the same return identity across hourly rechecks.
        original = folder/(version+".json")
        if original.exists():
            require(json_file(original)==ret,"RETURN_VERSION_CONFLICT")
        else:
            atomic(original,json_blob(ret))
        rows.append({"product_id":product,"version":version,"qa_state":qa["qa_state"]})
    report = {"schema":SCHEMA,"tenant":TENANT,"last_checked_utc":stamp(),
              "factory_versions_observed":len(products),"new_private_imports":added,
              "duplicate_versions_skipped":previous,
              "new_customer_packages_received":customer_added,
              "existing_customer_packages_verified":customer_existing,
              "new_native_private_previews_received":native_preview_added,
              "existing_native_private_previews_verified":native_preview_existing,
              "warehouse_versions_without_customer_bundle":customer_missing,
              "quality_approved":0,
              "pending_stage1_return":len(rows),"publicly_published":0,
              "store_product_created":0,"warehouse_bot_connected":True}
    atomic(root/"status.json",json_blob(report))
    return report


def feedback_site(root=DEST):
    root = target_root(root)
    folder = root/"returns"
    private_new(folder)
    rows = []
    for product in sorted(folder.iterdir()):
        require(product.is_dir() and not product.is_symlink()
                and RECIPE.fullmatch(product.name), "RETURN_DIRECTORY_INVALID")
        for item in sorted(product.iterdir()):
            require(item.is_file() and not item.is_symlink()
                    and item.suffix == ".json" and SHA.fullmatch(item.stem), "RETURN_NAME_INVALID")
            value = json_file(item,100_000)
            require(value.get("tenant")==TENANT and value.get("schema")==RETURN_SCHEMA
                    and value.get("product_id")==product.name
                    and value.get("source_sha256")==item.stem, "RETURN_IDENTITY_INVALID")
            rows.append(value)
            require(len(rows)<=MAX_ITEMS,"RETURN_COUNT_LIMIT")
    return json_blob({"schema":RETURN_SCHEMA,"tenant":TENANT,"returns":rows})


def receive_factory_returns(raw, root=VPS):
    require(len(raw) <= 1_000_000, "RETURN_REPORT_TOO_LARGE")
    data = json.loads(raw)
    require(data.get("tenant")==TENANT and data.get("schema")==RETURN_SCHEMA
            and isinstance(data.get("returns"),list) and len(data["returns"])<=MAX_ITEMS,
            "INVALID_MOJPLAYWIN_FEEDBACK")
    root=Path(root)
    clean_dir(root)
    intake = root/"design-intake"
    clean_dir(intake)
    recipient = intake/"mojplaywin-stage1-quality-returns"
    private_new(recipient)
    accepted, existing = 0, 0
    for row in data["returns"]:
        require(isinstance(row,dict)
                and row.get("tenant")==TENANT and row.get("schema")==RETURN_SCHEMA
                and row.get("stage")==1 and row.get("status")=="return_for_qa_completion"
                and row.get("issues")==list(ISSUES)
                and row.get("published") is False
                and row.get("factory_original_must_be_preserved") is True,
                "INVALID_STAGE1_RETURN_CONTRACT")
        product, version = row.get("product_id"),row.get("source_sha256")
        require(isinstance(product,str) and RECIPE.fullmatch(product)
                and isinstance(version,str) and SHA.fullmatch(version), "RETURN_UNSAFE_ID")
        stock=root/"production-warehouse/finished"/product/version
        clean_dir(stock)
        original=json_file(stock/"warehouse_manifest.json",100_000)
        require(original.get("artifact_sha256")==row.get("artifact_sha256")
                and original.get("source_sha256")==version
                and original.get("commercial_release") is False,
                "RETURN_NOT_OWNED_BY_FACTORY_STOCK")
        target=recipient/(product+"-"+version+".json")
        if target.exists() or target.is_symlink():
            require(json_file(target,100_000)==row,"STAGE1_RETURN_CONFLICT")
            existing+=1
        else:
            atomic(target,json_blob(row))
            accepted+=1
    report={"schema":RETURN_SCHEMA,"tenant":TENANT,
            "accepted_stage1_qa_returns":accepted,
            "previously_queued":existing,
            "factory_first_stage_intake":str(recipient.relative_to(root)),
            "factory_repair_executed":False,"products_deleted":0,
            "other_site_dispatch":False,"site_sales_enabled":False}
    return report


def triage_factory_stage1(root=VPS):
    """Actually consume site QA returns into durable actionable Stage-1 work.

    A work instruction and missing evidence checklist are an executed
    triage operation, not an executed creative repair or reviewer approval.
    The factory's native general designer accepts a different schema:
    never insert incomplete QA tickets into its auto-design input.
    """
    root = Path(root)
    clean_dir(root)
    intake = root/"design-intake/mojplaywin-stage1-quality-returns"
    clean_dir(intake)
    parent = root/"design-state"
    private_new(parent)
    dest = parent/"mojplaywin-stage1-qa-work"
    private_new(dest)
    lock_path = dest/".queue.lock"
    require(not lock_path.is_symlink(), "STAGE1_LOCK_SYMLINK")
    descriptor = os.open(str(lock_path), os.O_RDWR | os.O_CREAT | getattr(os,"O_NOFOLLOW",0), 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        items = []
        seen = set()
        for path in sorted(intake.iterdir()):
            require(path.is_file() and not path.is_symlink()
                    and path.name.endswith(".json"), "STAGE1_UNTRUSTED_ENTRY")
            row = json_file(path, 100_000)
            require(row.get("schema") == RETURN_SCHEMA
                    and row.get("tenant") == TENANT
                    and row.get("status") == "return_for_qa_completion"
                    and row.get("stage") == 1
                    and row.get("issues") == list(ISSUES)
                    and row.get("factory_original_must_be_preserved") is True
                    and row.get("published") is False, "STAGE1_WRONG_SCOPE")
            product, version = row.get("product_id"), row.get("source_sha256")
            require(isinstance(product,str) and RECIPE.fullmatch(product)
                    and isinstance(version,str) and SHA.fullmatch(version)
                    and path.name == product+"-"+version+".json"
                    and (product,version) not in seen, "STAGE1_IDENTITY_INVALID")
            seen.add((product,version))
            stock = root/"production-warehouse/finished"/product/version
            clean_dir(stock)
            original = json_file(stock/"warehouse_manifest.json", 100_000)
            artifact = stock/"product.zip"
            require(artifact.is_file() and not artifact.is_symlink()
                    and 0 < artifact.stat().st_size <= MAX_ZIP, "STAGE1_ORIGINAL_MISSING")
            require(original.get("source_sha256") == version
                    and original.get("artifact_sha256") == row.get("artifact_sha256")
                    and digest(artifact.read_bytes()) == row["artifact_sha256"]
                    and original.get("commercial_release") is False,
                    "STAGE1_SOURCE_NOT_VERIFIABLE")
            identity = product+"-"+version
            details = {
                "schema": RETURN_SCHEMA, "tenant": TENANT,
                "source_receipt_sha256": digest(json_blob(row)),
                "product_id":product, "version":version,
                "artifact_sha256":row["artifact_sha256"],
                "factory_entry_stage":1,
                "repair_priority":"needs_independent_review",
                "status":"awaiting_real_correction_evidence",
                "unresolved_codes":list(ISSUES),
                "actual_tasks":[
                    "Review original product content and scientific factual evidence; record reviewer and source links.",
                    "Verify copyright, licenses, ownership and third-party components with actual documents.",
                    "Obtain independently signed final commercial quality and owner publication decision.",
                    "If defects are found: correct original recipe/source in isolated factory workspace, rebuild and rerun complete tests.",
                ],
                "original_archive_preserved":True,
                "automated_approval":False, "production_rebuild_executed":False,
                "return_to_site_only_after_new_verified_source_version":True,
            }
            result = dest/(identity+".json")
            if result.exists() or result.is_symlink():
                require(result.is_file() and not result.is_symlink()
                        and json_file(result,100_000) == details, "STAGE1_WORK_ORDER_DRIFT")
            else:
                atomic(result,json_blob(details))
            items.append(details)
            require(len(items)<=MAX_ITEMS,"STAGE1_QUEUE_CAPACITY")
        state = {"schema":RETURN_SCHEMA,"tenant":TENANT,
                 "actual_site_returns_accepted":len(items),
                 "factory_stage1_work_items":len(items),
                 "unresolved_independent_review_items":len(items),
                 "physical_rebuild_claimed":False,"commercial_approval_claimed":False,
                 "all_source_archives_preserved":True,
                 "review_work_directory":"design-state/mojplaywin-stage1-qa-work",
                 "last_audit_utc":stamp()}
        atomic(dest/"stage1-status.json",json_blob(state))
        return state
    finally:
        os.close(descriptor)


PRODUCT_ORDER_SCHEMA="mpw.factory.three-product-requests.v1"
PRODUCT_ORDER_ID=re.compile(r"^MPWREQ-[a-f0-9]{20}$")
PRODUCT_ORDER_CYCLE=re.compile(r"^20[0-9]{6}(?:-r1)?$")
SITE_TRIAGE_SCHEMA="mpw.factory.native-site-order-technical-triage.v1"

def three_site_product_requests(root=DEST,cycle=None,*,require_fresh=False):
    """Three ACTUAL private site-origin QA rework requests, not buyer purchases.
    Ground each request in a byte-verified site stock and signed return ticket.
    A calendar-day cycle remains idempotent on hourly scheduler replays.
    """
    root=target_root(root)
    cycle=cycle or datetime.now(timezone.utc).strftime("%Y%m%d")
    require(bool(PRODUCT_ORDER_CYCLE.fullmatch(cycle)),"THREE_ORDERS_CYCLE_INVALID")
    try:day=datetime.strptime(cycle[:8],"%Y%m%d").date()
    except ValueError as exc:raise RuntimeError("THREE_ORDERS_CYCLE_INVALID") from exc
    folder=root/"returns"
    private_new(folder)
    candidates=[]
    for product in sorted(folder.iterdir()):
        require(product.is_dir() and not product.is_symlink() and RECIPE.fullmatch(product.name),
                "THREE_ORDERS_SITE_PRODUCT_UNSAFE")
        for row in sorted(product.iterdir()):
            require(row.is_file() and not row.is_symlink() and row.suffix==".json"
                    and SHA.fullmatch(row.stem),"THREE_ORDERS_SITE_VERSION_UNSAFE")
            ticket=json_file(row,100_000)
            version=row.stem
            received=root/"received"/product.name/version
            clean_dir(received)
            meta=json_file(received/"warehouse_manifest.json",100_000)
            archive=received/"product.zip"
            require(archive.is_file() and not archive.is_symlink()
                    and 0<archive.stat().st_size<=MAX_ZIP,"THREE_ORDERS_PRODUCT_MISSING")
            verify_stock(meta,product.name,version,archive.read_bytes())
            qa=json_file(received/"site_qa.json",100_000)
            require(ticket.get("schema")==RETURN_SCHEMA and ticket.get("tenant")==TENANT
                    and ticket.get("status")=="return_for_qa_completion"
                    and ticket.get("stage")==1
                    and ticket.get("source_sha256")==version
                    and ticket.get("artifact_sha256")==meta["artifact_sha256"]
                    and ticket.get("product_id")==product.name
                    and ticket.get("issues")==list(ISSUES)
                    and ticket.get("published") is False
                    and qa.get("qa_state")=="requires_factory_stage1_rework"
                    and qa.get("artifact_sha256")==meta["artifact_sha256"]
                    and qa.get("public_listing") is False
                    and qa.get("payment_enabled") is False,
                    "THREE_ORDERS_SITE_SOURCE_MISMATCH")
            candidates.append((product.name,version,meta["artifact_sha256"]))
            require(len(candidates)<=MAX_ITEMS,"THREE_ORDERS_SITE_INDEX_FULL")
    require(len(candidates)>=3,"THREE_ORDERS_NOT_ENOUGH_VERIFIED_SITE_PRODUCTS")
    # Use distinct site-verified product versions before replaying older work.
    # Past batches are immutable: they are NOT removed, replaced or marked done.
    # A valid same-day existing batch is revalidated below, never overwritten.
    outbound=root/"product-orders-outbound"
    private_new(outbound)
    path=outbound/(cycle+".json")
    history=sorted(outbound.glob("*.json"))
    historical_sources=set()
    for previous_path in history[-180:]:
        if (not PRODUCT_ORDER_CYCLE.fullmatch(previous_path.stem) or
                (previous_path.stem[:8], previous_path.stem.endswith("-r1")) >=
                (cycle[:8], cycle.endswith("-r1"))):
            continue
        require(previous_path.is_file() and not previous_path.is_symlink(),
                "THREE_ORDERS_HISTORY_UNSAFE")
        previous_batch=json_file(previous_path,100_000)
        require(previous_batch.get("schema")==PRODUCT_ORDER_SCHEMA
                and previous_batch.get("tenant")==TENANT
                and previous_batch.get("cycle")==previous_path.stem,
                "THREE_ORDERS_HISTORY_UNTRUSTED")
        past=previous_batch.get("requests")
        require(isinstance(past,list) and len(past)==3,
                "THREE_ORDERS_HISTORY_UNTRUSTED")
        for previous_row in past:
            require(isinstance(previous_row,dict)
                    and isinstance(previous_row.get("product_id"),str)
                    and RECIPE.fullmatch(previous_row["product_id"])
                    and isinstance(previous_row.get("source_sha256"),str)
                    and SHA.fullmatch(previous_row["source_sha256"]),
                    "THREE_ORDERS_HISTORY_UNTRUSTED")
            historical_sources.add((previous_row["product_id"],
                                    previous_row["source_sha256"]))
    fresh=[row for row in candidates if (row[0],row[1]) not in historical_sources]
    # If all three fresh versions are unavailable, keep the strict native
    # overlap/capacity block; never manufacture a fake "new" source.
    if require_fresh:
        require(len(fresh)>=3,"THREE_ORDERS_RESCUE_NO_NEW_SOURCE")
    pool=fresh if len(fresh)>=3 else candidates
    start=(day.toordinal()*3)%len(pool)
    chosen=[pool[(start+i)%len(pool)] for i in range(3)]
    rows=[]
    for slot,(product,version,sha) in enumerate(chosen,1):
        request_id="MPWREQ-"+digest((cycle+"|"+product+"|"+version).encode())[:20]
        rows.append({"slot":slot,"request_id":request_id,"product_id":product,
                     "source_sha256":version,"artifact_sha256":sha,
                     "kind":"verified_site_product_quality_rework",
                     "paid_customer_purchase":False,"public_distribution":False})
    assert len({row["request_id"] for row in rows})==3
    doc={"schema":PRODUCT_ORDER_SCHEMA,"tenant":TENANT,"cycle":cycle,
         "exact_product_requests":3,"requests":rows,
         "publications":0,"commercial_authorizations":0,
         "source":"site_verified_private_qa_returns",
         "real_customer_purchases":0}
    if path.exists() or path.is_symlink():
        # A site's verified stock may grow during the same UTC day. Once a
        # three-product batch exists, NEVER replace it based on today's changing
        # candidate count/rotation. Revalidate every original receipt against
        # the live private QA source before replaying the unchanged batch.
        previous=json_file(path,100_000)
        require(isinstance(previous,dict) and set(previous)==set(doc)
                and all(previous[k]==v for k,v in doc.items() if k!="requests"),
                "THREE_ORDERS_SITE_RECEIPT_CONFLICT")
        stored=previous.get("requests")
        require(isinstance(stored,list) and len(stored)==3,
                "THREE_ORDERS_SITE_RECEIPT_CONFLICT")
        valid_sources=set(candidates)
        for slot,row in enumerate(stored,1):
            require(isinstance(row,dict) and set(row)==set(rows[0]),
                    "THREE_ORDERS_SITE_RECEIPT_CONFLICT")
            product=row.get("product_id")
            version=row.get("source_sha256")
            sha=row.get("artifact_sha256")
            require(row.get("slot")==slot
                    and (product,version,sha) in valid_sources
                    and row.get("request_id")==
                        "MPWREQ-"+digest((cycle+"|"+product+"|"+version).encode())[:20]
                    and row.get("kind")=="verified_site_product_quality_rework"
                    and row.get("paid_customer_purchase") is False
                    and row.get("public_distribution") is False,
                    "THREE_ORDERS_SITE_RECEIPT_CONFLICT")
        require(len({row["request_id"] for row in stored})==3,
                "THREE_ORDERS_SITE_RECEIPT_CONFLICT")
        return json_blob(previous)
    atomic(path,json_blob(doc))
    return json_blob(doc)

def _native_order_engine(path=None):
    engine_file=Path(path) if path else (
        Path.home()/"factory-runtime/operations/production-instructions/generate-orders.py")
    require(engine_file.is_file() and not engine_file.is_symlink(),
            "SITE_ORDER_NATIVE_ENGINE_MISSING")
    spec=importlib.util.spec_from_file_location("mpw_native_factory_wo_engine",engine_file)
    engine=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine


def _site_order_proof(root,order,engine,proof_dir):
    """Compute immutable factual engineering evidence, NOT a release attestation."""
    ident=order.get("id")
    product=order.get("source_product_id")
    version=order.get("source_sha256")
    original_sha=order.get("source_artifact_sha256")
    require(isinstance(ident,str) and bool(engine.ORDER_RE.fullmatch(ident+".json"))
            and isinstance(product,str) and RECIPE.fullmatch(product)
            and isinstance(version,str) and SHA.fullmatch(version)
            and isinstance(original_sha,str) and SHA.fullmatch(original_sha)
            and order.get("origin")=="mojplaywin-site-qa-return"
            and order.get("requesting_site")=="mojplaywin.com"
            and order.get("instruction_kind")=="site_product_rework_work_order"
            and order.get("manufacturing_qa_passed") is False
            and order.get("publication_approved") is False
            and order.get("public_distribution_allowed") is False,
            "SITE_ORDER_SCOPE_OR_RELEASE_GATE_INVALID")
    stock=root/"production-warehouse/finished"/product/version
    clean_dir(stock)
    manifest=json_file(stock/"warehouse_manifest.json",100000)
    zipfile_path=stock/"product.zip"
    require(zipfile_path.is_file() and not zipfile_path.is_symlink()
            and 0 < zipfile_path.stat().st_size <= MAX_ZIP,"SITE_ORDER_ORIGINAL_ZIP_MISSING")
    raw=zipfile_path.read_bytes()
    verify_stock(manifest,product,version,raw)
    require(manifest["artifact_sha256"]==original_sha,"SITE_ORDER_ORIGINAL_SHA_MISMATCH")
    feedback=root/"design-intake/mojplaywin-stage1-quality-returns"/(product+"-"+version+".json")
    ticket=json_file(feedback,100000)
    require(ticket.get("schema")==RETURN_SCHEMA and ticket.get("tenant")==TENANT
            and ticket.get("product_id")==product
            and ticket.get("source_sha256")==version
            and ticket.get("artifact_sha256")==original_sha
            and ticket.get("status")=="return_for_qa_completion"
            and ticket.get("issues")==list(ISSUES)
            and ticket.get("published") is False
            and ticket.get("factory_original_must_be_preserved") is True,
            "SITE_ORDER_QUALITY_RETURN_UNVERIFIED")
    companion=customer_companion(root,product,version,original_sha)
    require(companion is not None,"SITE_ORDER_PRIVATE_TECHNICAL_PREVIEW_REQUIRED")
    report,bundle=companion
    kind=("static_native_review_only" if report.get("schema")==NATIVE_PREVIEW_SCHEMA
          else "cli_smoke_tested_calculator_only")
    proof={"schema":SITE_TRIAGE_SCHEMA,"tenant":TENANT,"work_order":ident,
           "work_order_fingerprint":order["fingerprint"],
           "source_product_id":product,"source_sha256":version,
           "original_zip_sha256":original_sha,
           "private_review_package_sha256":digest(bundle),
           "review_scope":kind,"source_archive_integrity_verified":True,
           "private_pack_independently_verified":True,
           "source_version_preserved":True,"substantive_source_rebuild_verified":False,
           "independent_domain_functionality_approved":False,
           "asset_ownership_and_licenses_cleared":False,
           "human_review_signed":False,"owner_publication_approved":False,
           "manufacturing_qa_for_rework_passed":False,
           "customer_sale_authorized":False,"public_distribution_allowed":False,
           "remaining_issues":list(ISSUES),
           "next_action":"qualified_specialist_review_then_actual_rework_if_required"}
    p=proof_dir/(ident+".json")
    if p.exists() or p.is_symlink():
        require(json_file(p,100000)==proof,"SITE_ORDER_TRIAGE_RECEIPT_COLLISION")
    else:
        engine.atomic_json(p,proof)
    return digest(json_blob(proof)),kind


def triage_site_work_orders(root=VPS,engine_path=None):
    """Advance genuine source-verified old WOs to a bounded specialist-review queue.

    Only original source and QA receipts are validated here. No claimed repair,
    specialist signature, finished product, purchase or commercial release.
    """
    root=Path(root)
    clean_dir(root)
    engine=_native_order_engine(engine_path)
    area=root/"production-instructions"
    orders=area/"orders"
    clean_dir(area);clean_dir(orders)
    proof_dir=area/"mojplaywin-source-technical-triage"
    private_new(proof_dir)
    locked=area/".orders.lock"
    require(not locked.is_symlink(),"SITE_ORDER_TRIAGE_LOCK_SYMLINK")
    outcomes={"source_orders_examined":0,"new_source_triages":0,
              "prior_source_triages_reverified":0,
              "triage_blocked_missing_technical_evidence":0,
              "work_orders_completed_verified":0,
              "manufacturing_qa_claimed":False,
              "public_sales_approved":False,
              "owner_rights_review_still_required":True}
    with locked.open("a+b") as fd:
        fcntl.flock(fd.fileno(),fcntl.LOCK_EX)
        rows=[p for p in sorted(orders.iterdir())]
        for p in rows:
            require(p.is_file() and not p.is_symlink()
                    and engine.ORDER_RE.fullmatch(p.name),"SITE_ORDER_TRIAGE_UNSAFE_FILENAME")
            row=engine.validate_old(p)
            if row.get("requesting_site")!="mojplaywin.com":
                continue
            require(row.get("origin")=="mojplaywin-site-qa-return",
                    "SITE_ORDER_TRIAGE_FOREIGN_SITE_ORDER")
            if row.get("status")=="completed_verified":
                continue
            outcomes["source_orders_examined"]+=1
            try:
                proof_sha,kind=_site_order_proof(root,row,engine,proof_dir)
            except (RuntimeError,OSError,ValueError,KeyError,TypeError) as error:
                outcomes["triage_blocked_missing_technical_evidence"]+=1
                # Never invent a proof or loosen an order on an inspection failure.
                continue
            if row.get("status")=="blocked_rework":
                require(row.get("technical_triage_evidence_sha256")==proof_sha,
                        "SITE_ORDER_TRIAGE_STATE_EVIDENCE_MISMATCH")
                outcomes["prior_source_triages_reverified"]+=1
                continue
            require(row.get("status") in ("issued","in_engineering"),
                    "SITE_ORDER_TRIAGE_STATUS_UNEXPECTED")
            record=dict(row,status="blocked_rework",
                        technical_triage_evidence_sha256=proof_sha,
                        technical_triage_scope=kind,
                        rework_awaits_human_domain_and_rights_review=True)
            engine.atomic_json(p,record)
            outcomes["new_source_triages"]+=1
    return {"schema":SITE_TRIAGE_SCHEMA,"tenant":TENANT,**outcomes}


def _prior_site_order_has_real_triage(root,order):
    """A status label by itself can NEVER free a backlog slot."""
    if order.get("status")!="blocked_rework":
        return False
    version=order.get("source_sha256")
    ident=order.get("id")
    proof_file=root/"production-instructions/mojplaywin-source-technical-triage"/(ident+".json")
    if not proof_file.exists():
        return False
    proof=json_file(proof_file,100000)
    return (proof.get("schema")==SITE_TRIAGE_SCHEMA
            and proof.get("tenant")==TENANT
            and proof.get("work_order")==ident
            and proof.get("work_order_fingerprint")==order.get("fingerprint")
            and proof.get("source_product_id")==order.get("source_product_id")
            and proof.get("source_sha256")==version
            and proof.get("original_zip_sha256")==order.get("source_artifact_sha256")
            and proof.get("source_archive_integrity_verified") is True
            and proof.get("private_pack_independently_verified") is True
            and proof.get("manufacturing_qa_for_rework_passed") is False
            and proof.get("customer_sale_authorized") is False
            and proof.get("owner_publication_approved") is False
            and order.get("technical_triage_evidence_sha256")==digest(json_blob(proof)))


def receive_three_product_requests(raw,root=VPS,engine_path=None,max_active=300):
    """Bind three verified site product rework orders to the existing native
    factory WO engine under its real lock; never count them as buyer orders.
    Prior unresolved three-site batches prevent backlog amplification.
    """
    require(0<len(raw)<=160000,"THREE_ORDERS_BATCH_LIMIT")
    batch=json.loads(raw)
    require(isinstance(batch,dict) and batch.get("schema")==PRODUCT_ORDER_SCHEMA
            and batch.get("tenant")==TENANT and batch.get("exact_product_requests")==3
            and batch.get("source")=="site_verified_private_qa_returns"
            and batch.get("real_customer_purchases")==0
            and batch.get("commercial_authorizations")==0
            and batch.get("publications")==0,
            "THREE_ORDERS_BATCH_SCHEMA")
    cycle=batch.get("cycle")
    require(isinstance(cycle,str) and bool(PRODUCT_ORDER_CYCLE.fullmatch(cycle)),
            "THREE_ORDERS_CYCLE_INVALID")
    rows=batch.get("requests")
    require(isinstance(rows,list) and len(rows)==3 and
            {r.get("slot") for r in rows if isinstance(r,dict)}=={1,2,3},
            "THREE_ORDERS_REQUEST_COUNT")
    seen=set()
    root=Path(root)
    clean_dir(root)
    validated=[]
    for row in rows:
        product,version,sha=row.get("product_id"),row.get("source_sha256"),row.get("artifact_sha256")
        require(isinstance(product,str) and RECIPE.fullmatch(product)
                and isinstance(version,str) and SHA.fullmatch(version)
                and isinstance(sha,str) and SHA.fullmatch(sha)
                and row.get("kind")=="verified_site_product_quality_rework"
                and row.get("paid_customer_purchase") is False
                and row.get("public_distribution") is False
                and row.get("request_id")=="MPWREQ-"+digest(
                    (cycle+"|"+product+"|"+version).encode())[:20],
                "THREE_ORDERS_REQUEST_INVALID")
        require((product,version) not in seen,"THREE_ORDERS_DUPLICATE_SOURCE")
        seen.add((product,version))
        stock=root/"production-warehouse/finished"/product/version
        clean_dir(stock)
        manifest=json_file(stock/"warehouse_manifest.json",100000)
        artifact=stock/"product.zip"
        require(artifact.is_file() and not artifact.is_symlink()
                and 0<artifact.stat().st_size<=MAX_ZIP,"THREE_ORDERS_FACTORY_STOCK_MISSING")
        verify_stock(manifest,product,version,artifact.read_bytes())
        require(manifest["artifact_sha256"]==sha,"THREE_ORDERS_FACTORY_SHA_MISMATCH")
        feedback=root/"design-intake/mojplaywin-stage1-quality-returns"/(product+"-"+version+".json")
        original=json_file(feedback,100000)
        require(original.get("schema")==RETURN_SCHEMA and original.get("tenant")==TENANT
                and original.get("source_sha256")==version
                and original.get("artifact_sha256")==sha
                and original.get("status")=="return_for_qa_completion"
                and original.get("issues")==list(ISSUES),
                "THREE_ORDERS_UNVERIFIED_SITE_FEEDBACK")
        # Bind a native WO to the family actually declared by the verified VPS
        # manufacturing manifest, never to a guessed website category.
        family=manifest.get("family_id")
        family=(family if isinstance(family,str) and
                re.fullmatch(r"F(?:0[1-9]|[1-3][0-9]|40)",family) else None)
        validated.append(dict(row,verified_factory_family=family))
    engine=_native_order_engine(engine_path)
    area=root/"production-instructions"
    orderdir=area/"orders"
    clean_dir(area);clean_dir(orderdir)
    receipt_dir=area/"mojplaywin-site-product-batches"
    private_new(receipt_dir)
    with (area/".orders.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        entries=[]
        for file in sorted(orderdir.iterdir()):
            require(file.is_file() and not file.is_symlink()
                    and bool(engine.ORDER_RE.fullmatch(file.name)),
                    "THREE_ORDERS_NATIVE_ENTRY_UNSAFE")
            entries.append(engine.validate_old(file))
        same=[x for x in entries if x.get("requesting_site")=="mojplaywin.com"
              and x.get("bridge_cycle")==cycle]
        require(len(same) in (0,3),"THREE_ORDERS_PARTIAL_NATIVE_BATCH")
        if same:
            by_slot={r["bridge_slot"]:r for r in same}
            require(set(by_slot)=={1,2,3} and all(
                by_slot[i]["site_request_id"]==row["request_id"]
                and by_slot[i]["source_product_id"]==row["product_id"]
                and by_slot[i]["source_sha256"]==row["source_sha256"]
                for i,row in enumerate(validated,1)), "THREE_ORDERS_NATIVE_REPLAY_CONFLICT")
            order_ids=[by_slot[i]["id"] for i in (1,2,3)]
            action="already_admitted"
        else:
            other_active=[x for x in entries if x.get("requesting_site")=="mojplaywin.com"
                         and x["status"]!="completed_verified"]
            pending=sum(x["status"]!="completed_verified"
                        and not engine.consumes_research_capacity(x) for x in entries)
            distinct_old={(x.get("source_product_id"),x.get("source_sha256"))
                          for x in other_active}
            overlap=any((x["product_id"],x["source_sha256"]) in distinct_old
                        for x in validated)
            if overlap:
                action="waiting_for_distinct_site_sources";order_ids=[]
            else:
                serial=max((int(x["id"][3:]) for x in entries),default=0)
                order_ids=[]
                for slot,row in enumerate(validated,1):
                    serial+=1
                    oid="WO-"+str(serial).zfill(8)
                    task={"origin":"mojplaywin-site-qa-return",
                          "requesting_site":"mojplaywin.com",
                          "bridge_cycle":cycle,"bridge_slot":slot,
                          "site_request_id":row["request_id"],
                          "source_product_id":row["product_id"],
                          "source_sha256":row["source_sha256"],
                          "source_artifact_sha256":row["artifact_sha256"],
                          "phase":"engineering_specification",
                          "subject":"Repair and re-verify existing site product "+row["product_id"],
                          "instruction":"Use linked site Stage-1 QA return to investigate scientific/content quality, licensing and commercial defects. Rebuild only if evidence justifies it. Preserve original version and independently rerun functional tests.",
                          "acceptance":["Verified existing source and QA return receipt",
                                        "Real correction or justified outstanding blocker",
                                        "Independent quality and rights review before sale",
                                        "Never release publicly without owner authorization"],
                          "technical_product_release":False}
                    if row["verified_factory_family"] is not None:
                        task["family_id"]=row["verified_factory_family"]
                    record=dict(task,schema=engine.SCHEMA,id=oid,
                        fingerprint=engine.fingerprint(task),
                        created_utc=engine.stamp(),status="issued",
                        instruction_kind="site_product_rework_work_order",
                        independent_of_websites=False,
                        requires_customer_order=False,api_required=False,
                        manufacturing_qa_passed=False,publication_approved=False,
                        public_distribution_allowed=False,warehouse_goods_created=False)
                    engine.atomic_json(orderdir/(oid+".json"),record)
                    order_ids.append(oid)
                action="three_native_product_orders_created"
        result={"schema":PRODUCT_ORDER_SCHEMA,"tenant":TENANT,"cycle":cycle,
                "received_verified_site_requests":3,"native_product_orders":order_ids,
                "new_native_orders":3 if action=="three_native_product_orders_created" else 0,
                "status":action,"real_paid_customer_orders":0,
                "factory_finished_products_claimed":0,
                "sales_or_publication_enabled":False}
        target=receipt_dir/(cycle+".json")
        if target.exists() or target.is_symlink():
            prior=json_file(target)
            if prior.get("native_product_orders") and prior.get("native_product_orders")!=order_ids:
                raise RuntimeError("THREE_ORDERS_RECEIPT_COLLISION")
        engine.atomic_json(target,result)
    return result

def main():
    require(len(sys.argv)==2, "COURIER_MODE_REQUIRED")
    mode=sys.argv[1]
    if mode=="vps-export":
        sys.stdout.buffer.write(export_factory())
    elif mode.startswith("vps-export-page-"):
        match=re.fullmatch(r"vps-export-page-(0|[1-9]|1[0-6])",mode)
        require(match is not None, "WAREHOUSE_PRIVATE_BATCH_PAGE_INVALID")
        sys.stdout.buffer.write(export_factory(page=int(match.group(1))))
    elif mode=="site-import":
        import_site(sys.stdin.buffer.read(MAX_PACKAGE+1))
        print("MPW_COURIER_SITE_INGEST=PASS", file=sys.stderr)
    elif mode=="site-feedback":
        sys.stdout.buffer.write(feedback_site())
    elif mode=="vps-return":
        report=receive_factory_returns(sys.stdin.buffer.read(1_000_001))
        print("MPW_COURIER_FACTORY_STAGE1="+json.dumps(report,sort_keys=True))
    elif mode=="vps-triage":
        report=triage_factory_stage1()
        print("MPW_COURIER_FACTORY_TRIAGE="+json.dumps(report,sort_keys=True))
    elif mode=="vps-site-order-triage":
        report=triage_site_work_orders()
        print("MPW_NATIVE_ORDER_EVIDENCE_TRIAGE="+json.dumps(report,sort_keys=True))
    elif mode=="site-three-orders-export":
        sys.stdout.buffer.write(three_site_product_requests())
    elif mode=="site-three-orders-export-rescue":
        cycle=datetime.now(timezone.utc).strftime("%Y%m%d")+"-r1"
        sys.stdout.buffer.write(three_site_product_requests(cycle=cycle,require_fresh=True))
    elif mode=="vps-three-orders-import":
        result=receive_three_product_requests(sys.stdin.buffer.read(160001))
        print("MPW_COURIER_THREE_PRODUCT_ORDERS="+json.dumps(result,sort_keys=True))
    else:
        raise RuntimeError("INVALID_COURIER_MODE")


if __name__=="__main__":
    main()
