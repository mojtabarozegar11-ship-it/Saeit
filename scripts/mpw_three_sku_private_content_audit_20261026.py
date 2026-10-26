#!/usr/bin/env python3
"""Private, hash-bound technical content audit for the three existing MojPlayWin artifacts.

The audit stores metrics and defect identifiers only. It never emits customer content,
changes store copies, assigns professional scores, or certifies quality1000.
"""
import hashlib
import html.parser
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

IDS = (72, 225, 879)
BASE = Path("/home/githubops/factory-runtime/private/autonomous-product-cycle/design-intake/mpw-live-three-sku-qa")
SHA = re.compile(r"^[a-f0-9]{64}$")

def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()

def digest_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

class PageAudit(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = False
        self.title_text = 0
        self.h1_count = 0
        self.images = 0
        self.images_without_alt = 0
        self.local_links = []
        self.external_scripts = 0
        self.inline_scripts = 0
        self.script_open = False
        self.forms = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self.title = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "img":
            self.images += 1
            if not (a.get("alt") or "").strip():
                self.images_without_alt += 1
        elif tag in ("a", "link", "script"):
            target = a.get("href") if tag != "script" else a.get("src")
            if target and not re.match(r"^(?:[a-z]+:|//|#)", target, re.I):
                self.local_links.append(target.split("?",1)[0].split("#",1)[0])
            if tag == "script":
                if a.get("src"):
                    if re.match(r"^(?:https?:)?//", a["src"], re.I):
                        self.external_scripts += 1
                else:
                    self.inline_scripts += 1
                    self.script_open = True
        elif tag == "form":
            self.forms += 1
    def handle_endtag(self, tag):
        if tag == "title":
            self.title = False
        if tag == "script":
            self.script_open = False
    def handle_data(self, data):
        if self.title and data.strip():
            self.title_text += len(data.strip())

def audit_pdf(path):
    from PyPDF2 import PdfReader
    reader = PdfReader(str(path), strict=False)
    page_chars = []
    page_hashes = []
    replacement_chars = 0
    extraction_errors = 0
    words = 0
    references = 0
    toc_signals = 0
    headings = 0
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
            extraction_errors += 1
        normalized = re.sub(r"\s+", " ", text).strip()
        page_chars.append(len(normalized))
        words += len(normalized.split())
        replacement_chars += text.count("\ufffd")
        if normalized:
            page_hashes.append(digest_bytes(normalized.casefold().encode("utf-8")))
        references += len(re.findall(r"(?:https?://|doi\s*:\s*|10\.\d{4,9}/)", text, re.I))
        toc_signals += len(re.findall(r"\b(?:contents|table of contents|فهرست)\b", text, re.I))
        headings += len(re.findall(r"(?m)^\s*(?:chapter|section|فصل)\s+[0-9۰-۹IVX]+\b", text, re.I))
    page_count = len(reader.pages)
    nonblank = sum(n >= 40 for n in page_chars)
    duplicates = len(page_hashes) - len(set(page_hashes))
    low_text = [i + 1 for i, n in enumerate(page_chars) if 0 < n < 40]
    checks = {
        "reader_opened": page_count > 0 and not reader.is_encrypted,
        "page_text_extraction_coverage_ge_95pct": page_count > 0 and nonblank / page_count >= .95,
        "no_page_extraction_errors": extraction_errors == 0,
        "duplicate_nonempty_pages_absent": duplicates == 0,
        "replacement_characters_absent": replacement_chars == 0,
        "bibliography_or_reference_markers_found": references > 0,
        "structure_markers_found": headings > 0 or toc_signals > 0,
    }
    return {
        "format": "pdf", "sha256": digest_file(path), "bytes": path.stat().st_size,
        "page_count": page_count, "extracted_word_count": words,
        "pages_with_text_ge_40_chars": nonblank, "text_coverage": round(nonblank / page_count, 4) if page_count else 0,
        "low_text_page_numbers": low_text[:100], "extraction_errors": extraction_errors,
        "duplicate_nonempty_pages": duplicates, "replacement_characters": replacement_chars,
        "reference_markers": references, "structure_markers": {"toc": toc_signals, "headings": headings},
        "checks": checks,
        "needs_specialist_review": ["factual_accuracy", "citation_validity", "scientific_depth", "layout_rendering", "accessibility", "commercial_rights_mapping"],
    }

def audit_zip(path):
    if not zipfile.is_zipfile(path):
        raise RuntimeError("ZIP_FORMAT_INVALID")
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        if not infos or len(infos) > 2000:
            raise RuntimeError("ZIP_MEMBER_COUNT_INVALID")
        names = set()
        unsafe = []
        total = 0
        for info in infos:
            p = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if p.is_absolute() or ".." in p.parts or "\\" in info.filename or info.filename in names or mode == 0o120000:
                unsafe.append(info.filename)
            names.add(info.filename)
            total += info.file_size
        if total > 512 * 1024 * 1024:
            raise RuntimeError("ZIP_EXPANSION_LIMIT")
        bad_crc = z.testzip()
        html_files = [i for i in infos if i.filename.lower().endswith((".html", ".htm")) and i.file_size <= 2_000_000]
        pages = []
        missing_local = []
        for info in html_files[:50]:
            raw = z.read(info)
            parser = PageAudit()
            try:
                parser.feed(raw.decode("utf-8"))
            except UnicodeDecodeError:
                parser.feed(raw.decode("utf-8", errors="replace"))
            parent = PurePosixPath(info.filename).parent
            unresolved = []
            for ref in parser.local_links:
                if not ref:
                    continue
                candidate = PurePosixPath(ref)
                resolved = (parent / candidate)
                options = {str(resolved), str(candidate)}
                if not any(x in names for x in options):
                    unresolved.append(ref[:180])
            missing_local.extend(unresolved)
            pages.append({
                "file_sha256": digest_bytes(raw), "has_title": parser.title_text > 0,
                "h1_count": parser.h1_count, "image_count": parser.images,
                "images_without_alt": parser.images_without_alt, "forms": parser.forms,
                "inline_scripts": parser.inline_scripts, "external_scripts": parser.external_scripts,
                "local_refs_checked": len(parser.local_links), "missing_local_refs": len(unresolved),
            })
        checks = {
            "crc_passed": bad_crc is None,
            "unsafe_members_absent": not unsafe,
            "html_entrypoint_found": bool(html_files),
            "html_title_present": bool(pages) and all(p["has_title"] for p in pages),
            "accessible_image_alt_present": all(p["images_without_alt"] == 0 for p in pages),
            "local_asset_links_resolve": not missing_local,
        }
        return {
            "format": "zip", "sha256": digest_file(path), "bytes": path.stat().st_size,
            "member_count": len(infos), "uncompressed_bytes": total, "html_page_count": len(html_files),
            "unsafe_member_count": len(unsafe), "crc_failure": bad_crc,
            "missing_local_refs": missing_local[:100], "html_pages": pages,
            "checks": checks,
            "needs_specialist_review": ["gameplay", "responsive_browser_execution", "accessibility", "security", "asset_licenses", "commercial_rights_mapping"],
        }

def run(root=BASE):
    root = Path(root)
    results = []
    for ident in IDS:
        requests = root / "review-requests" / str(ident)
        files = sorted(requests.glob("*.json"))
        if len(files) != 1 or requests.is_symlink():
            raise RuntimeError("QA_RECEIPT_COUNT_INVALID_" + str(ident))
        receipt_path = files[0]
        if receipt_path.is_symlink() or not SHA.fullmatch(receipt_path.stem):
            raise RuntimeError("QA_RECEIPT_UNSAFE_" + str(ident))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        sha = receipt.get("copy_sha256")
        if receipt.get("product_id") != ident or sha != receipt_path.stem or receipt.get("original_sha256") != sha:
            raise RuntimeError("QA_RECEIPT_IDENTITY_INVALID_" + str(ident))
        artifact = root / "copies" / str(ident) / (sha + ".bin")
        if artifact.is_symlink() or not artifact.is_file() or digest_file(artifact) != sha:
            raise RuntimeError("QA_ARTIFACT_HASH_MISMATCH_" + str(ident))
        measured = audit_pdf(artifact) if ident in (72, 225) else audit_zip(artifact)
        passed = sum(measured["checks"].values())
        report = {
            "schema": "saeit.mpw.private-content-audit.v1", "sku": ident,
            "source_sha256": sha, "measured_artifact": measured,
            "mechanical_check_count": len(measured["checks"]), "mechanical_pass_count": passed,
            "professional_quality_score": None, "quality1000_verified": False,
            "legal_dossier_status": "owner_confirmed_complete",
            "legal_execution_status": "active",
            "sku_version_mapping_status": "execution_in_progress",
            "content_was_emitted_to_logs": False,
        }
        raw = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        report_hash = digest_bytes(raw)
        folder = root / "quality1000-rework" / str(ident) / sha / "content-audits"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = folder / (report_hash + ".json")
        if target.exists():
            if target.is_symlink() or target.read_bytes() != raw:
                raise RuntimeError("AUDIT_REPORT_CONFLICT_" + str(ident))
        else:
            target.write_bytes(raw)
            target.chmod(0o600)
        results.append({"sku": ident, "source_sha256": sha, "report_sha256": report_hash,
                        "format": measured["format"], "mechanical_pass": passed,
                        "mechanical_total": len(measured["checks"]), "quality1000_verified": False})
    print("MPW_PRIVATE_CONTENT_AUDIT=" + json.dumps(results, sort_keys=True))
    print("MPW_CONTENT_BYTES_EMITTED=0;MPW_LIVE_MUTATIONS=0;MPW_QUALITY1000_CERTIFIED=0")
    return results

if __name__ == "__main__":
    run()
