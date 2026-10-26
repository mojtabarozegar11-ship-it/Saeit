#!/usr/bin/env python3
"""Private, hash-bound technical content audit for the three existing MojPlayWin artifacts.

The audit stores metrics and defect identifiers only. It never emits customer content,
changes store copies, assigns professional scores, or certifies quality1000.
"""
import hashlib
import html.parser
import json
import re
import shutil
import statistics
import subprocess
import tempfile
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
        if tag in ("a", "link", "script", "img", "source", "video", "audio"):
            target = a.get("href") if tag in ("a", "link") else a.get("src")
            targets = [target]
            if tag == "video":
                targets.append(a.get("poster"))
            if tag in ("img", "source"):
                srcset = a.get("srcset") or ""
                if srcset and not srcset.lstrip().lower().startswith("data:"):
                    targets.extend(part.strip().split()[0] for part in srcset.split(",") if part.strip())
            for target in targets:
                if target and not re.match(r"^(?:[a-z]+:|//|#)", target, re.I):
                    self.local_links.append(target.split("?",1)[0].split("#",1)[0])
            if tag == "script":
                if a.get("src"):
                    if re.match(r"^(?:https?:)?//", a["src"], re.I):
                        self.external_scripts += 1
                else:
                    self.inline_scripts += 1
                    self.script_open = True
        if tag == "form":
            self.forms += 1
    def handle_endtag(self, tag):
        if tag == "title":
            self.title = False
        if tag == "script":
            self.script_open = False
    def handle_data(self, data):
        if self.title and data.strip():
            self.title_text += len(data.strip())

def ppm_pixel_metrics(raw):
    if not raw.startswith(b"P6"):
        raise ValueError("PPM_BINARY_P6_REQUIRED")
    pos = 0
    tokens = []
    while len(tokens) < 4:
        while pos < len(raw):
            if raw[pos] in b" \t\r\n":
                pos += 1
            elif raw[pos] == 35:
                end = raw.find(b"\n", pos)
                pos = len(raw) if end < 0 else end + 1
            else:
                break
        start = pos
        while pos < len(raw) and raw[pos] not in b" \t\r\n#":
            pos += 1
        if start == pos:
            raise ValueError("PPM_HEADER_INVALID")
        tokens.append(raw[start:pos])
    magic, width_raw, height_raw, maxval_raw = tokens
    width, height, maxval = int(width_raw), int(height_raw), int(maxval_raw)
    if magic != b"P6" or width <= 0 or height <= 0 or maxval != 255:
        raise ValueError("PPM_DIMENSIONS_OR_DEPTH_INVALID")
    if pos >= len(raw) or raw[pos] not in b" \t\r\n":
        raise ValueError("PPM_HEADER_SEPARATOR_MISSING")
    if raw[pos:pos + 2] == b"\r\n":
        pos += 2
    else:
        pos += 1
    pixels = raw[pos:]
    total = width * height
    if len(pixels) != total * 3:
        raise ValueError("PPM_PIXEL_LENGTH_INVALID")
    sample_step = max(1, total // 16000)
    sampled = nonwhite = colored = 0
    for pixel_index in range(0, total, sample_step):
        i = pixel_index * 3
        red, green, blue = pixels[i], pixels[i + 1], pixels[i + 2]
        sampled += 1
        if min(red, green, blue) < 245:
            nonwhite += 1
        if max(red, green, blue) - min(red, green, blue) >= 18:
            colored += 1
    nonwhite_ratio = nonwhite / sampled if sampled else 0.0
    return {
        "width": width, "height": height, "sampled_pixels": sampled,
        "nonwhite_ratio": round(nonwhite_ratio, 5),
        "colored_pixel_ratio": round(colored / sampled if sampled else 0.0, 5),
        "near_blank": nonwhite_ratio < 0.002,
    }


def bitmap_pixel_metrics(bitmap):
    width, height, channels, stride = bitmap.width, bitmap.height, bitmap.n_channels, bitmap.stride
    if width <= 0 or height <= 0 or channels < 3 or stride < width * channels:
        raise ValueError("PDFIUM_BITMAP_LAYOUT_INVALID")
    total = width * height
    sample_step = max(1, total // 16000)
    sampled = nonwhite = colored = 0
    buffer = bitmap.buffer
    for pixel_index in range(0, total, sample_step):
        y, x = divmod(pixel_index, width)
        offset = y * stride + x * channels
        first, second, third = buffer[offset], buffer[offset + 1], buffer[offset + 2]
        sampled += 1
        if min(first, second, third) < 245:
            nonwhite += 1
        if max(first, second, third) - min(first, second, third) >= 18:
            colored += 1
    nonwhite_ratio = nonwhite / sampled if sampled else 0.0
    return {"width": width, "height": height, "sampled_pixels": sampled,
            "nonwhite_ratio": round(nonwhite_ratio, 5),
            "colored_pixel_ratio": round(colored / sampled if sampled else 0.0, 5),
            "near_blank": nonwhite_ratio < 0.002}


def render_pdf_pages(path, expected_page_count):
    try:
        import pypdfium2 as pdfium
    except ImportError:
        pdfium = None
    if pdfium is not None:
        metrics = []
        render_errors = 0
        document = None
        try:
            document = pdfium.PdfDocument(str(path))
            page_count = len(document)
            if page_count != expected_page_count:
                return {"renderer_available": True, "renderer": "pypdfium2",
                        "rendered_page_count": 0, "page_count_matches": False,
                        "near_blank_page_numbers": [], "pages_with_color_signal": 0,
                        "mean_nonwhite_ratio": None, "render_errors": 0,
                        "render_failure": "RENDERER_PAGE_COUNT_MISMATCH"}
            for index in range(page_count):
                page = bitmap = None
                try:
                    page = document[index]
                    width, height = page.get_size()
                    bitmap = page.render(scale=320.0 / max(width, height))
                    metrics.append(bitmap_pixel_metrics(bitmap))
                except Exception:
                    render_errors += 1
                finally:
                    if bitmap is not None:
                        bitmap.close()
                    if page is not None:
                        page.close()
        except Exception:
            return {"renderer_available": True, "renderer": "pypdfium2",
                    "rendered_page_count": len(metrics), "page_count_matches": False,
                    "near_blank_page_numbers": [], "pages_with_color_signal": 0,
                    "mean_nonwhite_ratio": None, "render_errors": render_errors + 1,
                    "render_failure": "RENDERER_REJECTED_PDF"}
        finally:
            if document is not None:
                document.close()
        ratios = [item["nonwhite_ratio"] for item in metrics]
        return {"renderer_available": True, "renderer": "pypdfium2",
                "rendered_page_count": len(metrics),
                "page_count_matches": len(metrics) == expected_page_count,
                "render_errors": render_errors,
                "near_blank_page_numbers": [i + 1 for i, item in enumerate(metrics) if item["near_blank"]][:100],
                "pages_with_color_signal": sum(item["colored_pixel_ratio"] >= 0.01 for item in metrics),
                "mean_nonwhite_ratio": round(statistics.mean(ratios), 5) if ratios else None,
                "median_nonwhite_ratio": round(statistics.median(ratios), 5) if ratios else None,
                "render_failure": None if render_errors == 0 else "PAGE_RENDER_ERRORS"}
    renderer = shutil.which("pdftoppm")
    if renderer is None:
        return {"renderer_available": False, "renderer": None, "rendered_page_count": 0,
                "page_count_matches": False, "near_blank_page_numbers": [],
                "pages_with_color_signal": 0, "mean_nonwhite_ratio": None,
                "render_failure": "NO_PRIVATE_PDF_RENDERER"}
    with tempfile.TemporaryDirectory(prefix="mpw-private-render-") as temp:
        prefix = Path(temp) / "page"
        try:
            proc = subprocess.run([renderer, "-q", "-r", "36", "-scale-to", "320", str(path), str(prefix)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=210, check=False)
        except subprocess.TimeoutExpired:
            return {"renderer_available": True, "renderer": "pdftoppm", "rendered_page_count": 0,
                    "page_count_matches": False, "near_blank_page_numbers": [],
                    "pages_with_color_signal": 0, "mean_nonwhite_ratio": None,
                    "render_failure": "RENDER_TIMEOUT"}
        if proc.returncode != 0:
            return {"renderer_available": True, "renderer": "pdftoppm", "rendered_page_count": 0,
                    "page_count_matches": False, "near_blank_page_numbers": [],
                    "pages_with_color_signal": 0, "mean_nonwhite_ratio": None,
                    "render_failure": "RENDERER_REJECTED_PDF"}
        files = sorted(prefix.parent.glob("page-*.ppm"),
                       key=lambda p: int(re.search(r"-(\d+)\.ppm$", p.name).group(1)))
        metrics = []
        render_errors = 0
        for image in files:
            try:
                metrics.append(ppm_pixel_metrics(image.read_bytes()))
            except (OSError, ValueError, IndexError):
                render_errors += 1
        ratios = [item["nonwhite_ratio"] for item in metrics]
        return {"renderer_available": True, "renderer": "pdftoppm",
                "rendered_page_count": len(metrics), "page_count_matches": len(metrics) == expected_page_count,
                "render_errors": render_errors,
                "near_blank_page_numbers": [i + 1 for i, item in enumerate(metrics) if item["near_blank"]][:100],
                "pages_with_color_signal": sum(item["colored_pixel_ratio"] >= 0.01 for item in metrics),
                "mean_nonwhite_ratio": round(statistics.mean(ratios), 5) if ratios else None,
                "median_nonwhite_ratio": round(statistics.median(ratios), 5) if ratios else None,
                "render_failure": None if not render_errors else "PPM_DECODE_ERRORS"}



def graphic_drawing_signals_present(page_count, embedded_images, pages_with_vector_drawing,
                                       vector_drawing_operator_count):
    if embedded_images > 0:
        return True
    if page_count <= 0 or pages_with_vector_drawing <= 0:
        return False
    vector_page_threshold = max(1, (page_count * 4 + 4) // 5)
    return (pages_with_vector_drawing >= vector_page_threshold
            and vector_drawing_operator_count >= 8 * pages_with_vector_drawing)


def audit_pdf(path, expected_page_count=None, require_illustrations=False):
    from PyPDF2 import PdfReader
    reader = PdfReader(str(path), strict=False)
    page_chars = []
    page_hashes = []
    replacement_chars = 0
    extraction_errors = 0
    embedded_images = 0
    image_pages = 0
    image_scan_errors = 0
    vector_drawing_operator_count = 0
    pages_with_vector_drawing = 0
    graphics_scan_errors = 0
    words = 0
    references = 0
    toc_signals = 0
    headings = 0
    from PyPDF2.generic import ContentStream
    drawing_ops = {b"m", b"l", b"c", b"v", b"y", b"re", b"h", b"S", b"s",
                   b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}
    for page in reader.pages:
        try:
            page_images = page.images
            image_count = len(page_images)
            embedded_images += image_count
            if image_count:
                image_pages += 1
        except Exception:
            image_scan_errors += 1
        try:
            content = page.get_contents()
            operations = ContentStream(content, reader).operations if content else []
            path_count = sum(1 for operands, operator in operations if operator in drawing_ops)
            vector_drawing_operator_count += path_count
            if path_count >= 8:
                pages_with_vector_drawing += 1
        except Exception:
            graphics_scan_errors += 1
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
    visual_render = render_pdf_pages(path, page_count)
    checks = {
        "reader_opened": page_count > 0 and not reader.is_encrypted,
        "page_text_extraction_coverage_ge_95pct": page_count > 0 and nonblank / page_count >= .95,
        "no_page_extraction_errors": extraction_errors == 0,
        "duplicate_nonempty_pages_absent": duplicates == 0,
        "replacement_characters_absent": replacement_chars == 0,
        "all_pdf_pages_rendered": visual_render["renderer_available"] and visual_render["page_count_matches"] and visual_render.get("render_errors", 0) == 0,
    }
    is_picture_book = expected_page_count is not None and require_illustrations
    if not is_picture_book:
        # Preserve research-guide requirements for SKU 72 and all default PDF audits.
        checks["bibliography_or_reference_markers_found"] = references > 0
        checks["structure_markers_found"] = headings > 0 or toc_signals > 0
    if expected_page_count is not None:
        checks["page_count_matches_declared_product_spec"] = page_count == expected_page_count
    if require_illustrations:
        checks["graphic_drawing_signals_present"] = graphic_drawing_signals_present(
            page_count, embedded_images, pages_with_vector_drawing, vector_drawing_operator_count)
    return {
        "format": "pdf", "sha256": digest_file(path), "bytes": path.stat().st_size,
        "page_count": page_count, "extracted_word_count": words,
        "pages_with_text_ge_40_chars": nonblank, "text_coverage": round(nonblank / page_count, 4) if page_count else 0,
        "low_text_page_numbers": low_text[:100], "extraction_errors": extraction_errors,
        "duplicate_nonempty_pages": duplicates, "replacement_characters": replacement_chars,
        "reference_markers": references, "structure_markers": {"toc": toc_signals, "headings": headings},
        "expected_page_count": expected_page_count, "embedded_image_count": embedded_images,
        "pages_with_embedded_images": image_pages, "image_scan_errors": image_scan_errors,
        "vector_drawing_operator_count": vector_drawing_operator_count,
        "pages_with_vector_drawing": pages_with_vector_drawing,
        "graphics_scan_errors": graphics_scan_errors,
        "visual_render": visual_render,
        "contextual_exclusions": ([
            {"criterion": "bibliography_or_reference_markers_found", "reason": "Not required for an illustrated children's read-aloud picture book"},
            {"criterion": "structure_markers_found", "reason": "Chapter or table-of-contents markers are not applicable to this picture-book format"},
        ] if is_picture_book else []),
        "checks": checks,
        "needs_specialist_review": (
            ["story_accuracy", "read_aloud_rhythm", "child_appropriateness", "illustration_quality", "layout_rendering", "accessibility", "commercial_rights_mapping"]
            if is_picture_book else
            ["factual_accuracy", "citation_validity", "scientific_depth", "layout_rendering", "accessibility", "commercial_rights_mapping"]
        ),
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
            "needs_specialist_review": ["responsive_browser_execution", "navigation_integrity", "browser_console_errors", "accessibility", "security", "asset_licenses", "commercial_rights_mapping"],
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
        measured = (audit_pdf(artifact, expected_page_count=40, require_illustrations=True) if ident == 225
                    else audit_pdf(artifact)) if ident in (72, 225) else audit_zip(artifact)
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
                        "mechanical_total": len(measured["checks"]),
                        "failed_checks": [name for name, ok in measured["checks"].items() if not ok],
                        "embedded_image_count": measured.get("embedded_image_count"),
                        "pages_with_embedded_images": measured.get("pages_with_embedded_images"),
                        "image_scan_errors": measured.get("image_scan_errors"),
                        "vector_drawing_operator_count": measured.get("vector_drawing_operator_count"),
                        "pages_with_vector_drawing": measured.get("pages_with_vector_drawing"),
                        "graphics_scan_errors": measured.get("graphics_scan_errors"),
                        "rendered_page_count": measured.get("visual_render", {}).get("rendered_page_count"),
                        "rendered_page_count_matches": measured.get("visual_render", {}).get("page_count_matches"),
                        "near_blank_page_count": len(measured.get("visual_render", {}).get("near_blank_page_numbers", [])),
                        "pages_with_color_signal": measured.get("visual_render", {}).get("pages_with_color_signal"),
                        "render_failure": measured.get("visual_render", {}).get("render_failure"),
                        "quality1000_verified": False})
    print("MPW_PRIVATE_CONTENT_AUDIT=" + json.dumps(results, sort_keys=True))
    print("MPW_CONTENT_BYTES_EMITTED=0;MPW_LIVE_MUTATIONS=0;MPW_QUALITY1000_CERTIFIED=0")
    return results

if __name__ == "__main__":
    run()
