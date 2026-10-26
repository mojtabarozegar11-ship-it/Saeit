#!/usr/bin/env python3
"""Bounded, read-only *artifact* checks; immutable QA1000 rework tickets for three paid store SKUs.

Reads private factory copies, never touches storefront, orders, rights flags, or stock.
A technical check is NOT a professional 1000/1000 quality or paid-release approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile

IDS = (72, 225, 879)
SCHEMA = "saeit.mpw.three-retail-artifact-qa1000-rework.v1"
COPY_SCHEMA = "saeit.mpw.live-three-private-qa-copy.v1"
BASE = Path("/home/githubops/factory-runtime/private/autonomous-product-cycle/design-intake/mpw-live-three-sku-qa")
SHA = re.compile(r"^[a-f0-9]{64}$")
MAX_FILE = 150 * 1024 * 1024

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def ensure_private(path):
    if path.is_symlink():
        raise RuntimeError("UNSAFE_SYMLINK_FOLDER")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink():
        raise RuntimeError("UNSAFE_PRIVATE_FOLDER")
    os.chmod(path, 0o700)

def immutable_write(path, data):
    ensure_private(path.parent)
    if path.is_symlink():
        raise RuntimeError("PRIVATE_REPORT_SYMLINK")
    if path.exists():
        if not path.is_file() or path.read_bytes() != data:
            raise RuntimeError("IMMUTABLE_QA_RECEIPT_CONFLICT")
        return False
    fd, temp = tempfile.mkstemp(prefix=".mpw-qa1000-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, 0o600)
        try:
            os.link(temp, path)
            return True
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != data:
                raise RuntimeError("IMMUTABLE_QA_RECEIPT_CONFLICT")
            return False
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def inspect_pdf(path):
    result = {"format": "pdf", "prefix_verified": False, "pdfinfo_available": bool(shutil.which("pdfinfo")),
              "pdfinfo_passed": False, "page_count": None, "encrypted": None,
              "rendered_page_visual_review_verified": False, "substantive_text_review_verified": False}
    with path.open("rb") as stream:
        result["prefix_verified"] = stream.read(8).startswith(b"%PDF-")
    if not result["prefix_verified"]:
        raise RuntimeError("PDF_MISSING_MAGIC")
    if result["pdfinfo_available"]:
        proc = subprocess.run(["pdfinfo", str(path)], capture_output=True, timeout=35, check=False)
        if proc.returncode == 0:
            data = proc.stdout.decode("utf-8", errors="replace")
            m = re.search(r"^Pages:\s+(\d+)\s*$", data, re.M)
            enc = re.search(r"^Encrypted:\s+([a-zA-Z]+)", data, re.M)
            result["page_count"] = int(m.group(1)) if m else None
            result["encrypted"] = enc.group(1).lower() == "yes" if enc else None
            result["pdfinfo_passed"] = bool(result["page_count"] and result["page_count"] > 0 and result["encrypted"] is False)
        else:
            result["pdfinfo_failure"] = "PARSER_REJECTED"
    # VPS images may not include pdfinfo. Safely try already-installed Python parsers
    # without fetching packages or moving private book bytes off the factory.
    result["python_backend_passed"] = False
    result["python_backend"] = None
    if not result["pdfinfo_passed"]:
        import importlib
        import importlib.util
        for backend in ("pypdf", "PyPDF2", "fitz"):
            if importlib.util.find_spec(backend) is None:
                continue
            result["python_backend"] = backend
            try:
                module = importlib.import_module(backend)
                if backend == "fitz":
                    doc = module.open(str(path))
                    try:
                        count = len(doc)
                        encrypted = bool(doc.is_encrypted)
                    finally:
                        doc.close()
                else:
                    doc = module.PdfReader(str(path), strict=False)
                    encrypted = bool(doc.is_encrypted)
                    count = 0 if encrypted else len(doc.pages)
                if count > 0 and not encrypted:
                    result["page_count"] = count
                    result["encrypted"] = False
                    result["python_backend_passed"] = True
                    break
            except Exception:
                result["python_parser_failure"] = "PARSER_REJECTED"
    result["pdf_validation_passed"] = bool(
        result["pdfinfo_passed"] or result["python_backend_passed"])
    return result

def inspect_zip(path):
    result = {"format": "zip", "valid": False, "member_count": 0,
              "total_uncompressed_bytes": 0, "contains_readme": False,
              "contains_license": False, "contains_html": False,
              "browser_test_verified": False, "third_party_asset_rights_verified": False}
    if not zipfile.is_zipfile(path):
        raise RuntimeError("ZIP_FORMAT_INVALID")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if not 0 < len(infos) <= 2000:
            raise RuntimeError("ZIP_MEMBER_COUNT_INVALID")
        names = set()
        size = 0
        for item in infos:
            name = item.filename
            parts = PurePosixPath(name)
            mode = (item.external_attr >> 16) & 0o170000
            if name.startswith("/") or "\\" in name or ".." in parts.parts or name in names or mode == 0o120000:
                raise RuntimeError("ZIP_UNSAFE_MEMBER")
            names.add(name)
            size += item.file_size
            if size > 512 * 1024 * 1024:
                raise RuntimeError("ZIP_EXPANSION_LIMIT")
        if archive.testzip() is not None:
            raise RuntimeError("ZIP_CRC_FAILED")
    lowercase = [v.lower() for v in names]
    result.update({"valid": True, "member_count": len(names), "total_uncompressed_bytes": size,
                   "contains_readme": any("readme" in v for v in lowercase),
                   "contains_license": any("license" in v or "licence" in v for v in lowercase),
                   "contains_html": any(v.endswith((".html", ".htm")) for v in lowercase)})
    return result

def make_order(ident, row, copy, facts):
    is_pdf = ident in (72, 225)
    stages = [
        {"task": "verify byte-for-byte source provenance and immutable customer-copy checksum",
         "state": "measured", "evidence": "sha256 and file-length match exact SKU receipt"},
        {"task": "inspect full content and original editable/source materials", "state": "pending"},
        {"task": "document exact-version authorship, component licenses, and sale rights", "state": "pending"},
        {"task": "independent adversarial quality review against 100 distinct criteria", "state": "pending"},
        {"task": "execute and authenticate all required QC1000 scenarios and expert evidence", "state": "pending"},
        {"task": "produce version-bound technically improved candidate without touching live SKU", "state": "pending"},
        {"task": "test customer checkout through paid invoice and private delivery without real transfer until owner authorizes", "state": "pending"}
    ]
    if is_pdf:
        stages.insert(2, {"task": "render every PDF page and check glyphs, layout, cropping and figures", "state": "pending"})
        stages.insert(3, {"task": "check subject accuracy, original citations, TOC, accessibility and editorial quality", "state": "pending"})
    else:
        stages.insert(2, {"task": "execute isolated responsive browser tests and inspect every archive asset", "state": "pending"})
        stages.insert(3, {"task": "repair accessibility, package documentation and static-site security defects", "state": "pending"})
    return {
        "schema": SCHEMA, "site": "mojplaywin.com", "product_id": ident,
        "product_title": row.get("product_title", ""),
        "source_store_product_id": ident, "current_product_stays_published": True,
        "source_file_sha256": row["original_sha256"], "factory_copy_sha256": digest(copy),
        "factory_copy_bytes": copy.stat().st_size, "source_receipt_is_private": True,
        "inspection": facts, "quality_goal": 1000,
        "quality_policy": "saeit.factory.active-quality-1000.v3",
        "quality_criteria": [{"id": "Q%03d" % i, "professional_score": None, "approval": "PENDING_REAL_EVIDENCE"}
                             for i in range(1, 101)],
        "professional_quality_score": None, "quality_1000_verified": False,
        "independent_specialist_reviews_verified": False,
        "owner_version_release_approval_recorded": False,
        "licensed_commercial_version_cleared": False,
        "automatic_approval_for_existing_store": False,
        "can_replace_live_store_file": False,
        "paid_customer_orders_modified": False,
        "state": "REWORK_1000_QUALITY_REQUIRED",
        "rework_stages": stages
    }

def run(root=BASE):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("THREE_SKU_COPY_INTAKE_MISSING")
    result = []
    for ident in IDS:
        requests = root / "review-requests" / str(ident)
        if requests.is_symlink() or not requests.is_dir():
            raise RuntimeError("QA_STORE_ORIGIN_RECEIPT_MISSING_" + str(ident))
        files = sorted(requests.glob("*.json"))
        if not files or len(files) > 50:
            raise RuntimeError("QA_STORE_ORIGIN_RECEIPT_COUNT_" + str(ident))
        versions = []
        for receipt in files:
            if receipt.is_symlink() or not SHA.fullmatch(receipt.stem) or receipt.stat().st_size > 20000:
                raise RuntimeError("QA_UNSAFE_ORIGIN_RECEIPT")
            row = json.loads(receipt.read_text(encoding="utf-8"))
            sha = row.get("copy_sha256")
            if (row.get("schema") != COPY_SCHEMA or row.get("product_id") != ident
                    or row.get("original_sha256") != sha or sha != receipt.stem
                    or not isinstance(sha, str) or not SHA.fullmatch(sha)
                    or row.get("storefront_unchanged") is not True
                    or row.get("live_replacement_authorized") is not False):
                raise RuntimeError("QA_ORIGIN_RECEIPT_NOT_VALID_" + str(ident))
            copy = root / "copies" / str(ident) / (sha + ".bin")
            if (copy.is_symlink() or not copy.is_file() or
                    copy.stat().st_size != row.get("bytes") or
                    not 0 < copy.stat().st_size <= MAX_FILE or digest(copy) != sha):
                raise RuntimeError("QA_SOURCE_COPY_CHANGED_" + str(ident))
            if ident in (72, 225):
                facts = inspect_pdf(copy)
            else:
                facts = inspect_zip(copy)
            ticket = make_order(ident, row, copy, facts)
            raw = (json.dumps(ticket, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
            doc_hash = hashlib.sha256(raw).hexdigest()
            dst = root / "quality1000-rework" / str(ident) / sha / (doc_hash + ".json")
            immutable_write(dst, raw)
            versions.append({"sha256": sha, "format": facts["format"],
                             "pdf_parser_available": facts.get("pdfinfo_available"),
                             "pdf_parser_passed": facts.get("pdf_validation_passed"),
                             "pdf_python_backend": facts.get("python_backend"),
                             "pdf_pages": facts.get("page_count"),
                             "pdf_parser_failure": facts.get("pdfinfo_failure"),
                             "zip_crc_passed": facts.get("valid"),
                             "quality1000_verified": False,
                             "rework_ticket_sha256": doc_hash})
        result.append({"sku": ident, "versions_in_factory": len(versions), "versions": versions})
    print("MPW_THREE_QA1000_INTAKE=" + json.dumps(result, sort_keys=True))
    print("MPW_LIVE_STORE_MUTATIONS=0;MPW_PAID_RELEASE_APPROVALS=0;MPW_QA1000_CERTIFIED=0")
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--private-root", default=str(BASE))
    a = p.parse_args()
    run(Path(a.private_root))

if __name__ == "__main__":
    main()
