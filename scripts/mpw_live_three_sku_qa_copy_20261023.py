#!/usr/bin/env python3
"""Read-only copies of three live MojPlayWin SKUs to private VPS factory QA.

No storefront/model/checkout writes. No automatic substitution of live files.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tarfile
import tempfile
import zipfile
import zlib

IDS = (72, 225, 879)
SCHEMA = "saeit.mpw.live-three-private-qa-copy.v1"
MAX_FILE = 150 * 1024 * 1024
BASE = Path("/home/githubops/factory-runtime/private/autonomous-product-cycle/design-intake/mpw-live-three-sku-qa")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def private_dir(path):
    if path.is_symlink():
        raise RuntimeError("QA_UNSAFE_DIRECTORY_LINK")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("QA_PRIVATE_DIRECTORY_INVALID")
    os.chmod(path, 0o700)


def write_once(path, data):
    private_dir(path.parent)
    if path.is_symlink():
        raise RuntimeError("QA_RECEIPT_LINK")
    fd, tmp = tempfile.mkstemp(prefix=".qa-atomic-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        try:
            os.link(tmp, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != data:
                raise RuntimeError("QA_IMMUTABLE_RECEIPT_CONFLICT")
    finally:
        os.unlink(tmp)


def validate_manifest(obj):
    if not isinstance(obj, dict) or obj.get("schema") != SCHEMA or obj.get("site") != "mojplaywin.com":
        raise RuntimeError("QA_WRONG_SOURCE")
    rows = obj.get("products")
    if not isinstance(rows, list) or len(rows) != 3 or tuple(x.get("id") for x in rows if isinstance(x, dict)) != IDS:
        raise RuntimeError("QA_EXACT_THREE_REQUIRED")
    for x in rows:
        if (not isinstance(x.get("size"), int) or isinstance(x["size"], bool)
                or not 0 < x["size"] <= MAX_FILE
                or not isinstance(x.get("sha256"), str) or len(x["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in x["sha256"])
                or not isinstance(x.get("title"), str) or len(x["title"]) > 250):
            raise RuntimeError("QA_MANIFEST_INVALID")
    return rows


def site_export():
    home = Path("/home/zomorod2").resolve(strict=True)
    app = home / "Saeit-staging"
    if app.is_symlink() or not app.is_dir():
        raise RuntimeError("QA_SITE_APP_MISSING")
    os.chdir(app)
    sys.path.insert(0, str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from core.models import Product
    from mpw_commerce.buyer_orders import _eligible
    from mpw_commerce.downloads import _private_file
    from types import SimpleNamespace

    copies = []
    for pk in IDS:
        item = Product.objects.get(pk=pk)
        if not item.active or item.currency != "USD" or not _eligible(item):
            raise RuntimeError("QA_SKU_NO_LONGER_ELIGIBLE_" + str(pk))
        path = Path(_private_file(SimpleNamespace(product=item)))
        real = path.resolve(strict=True)
        if (path.is_symlink() or not real.is_file() or home not in real.parents
                or any(part in ("mojplaywin.com", "public_html") for part in real.relative_to(home).parts)):
            raise RuntimeError("QA_NOT_PRIVATE_OR_UNSAFE_FILE_" + str(pk))
        mode = real.stat()
        if not stat.S_ISREG(mode.st_mode) or not 0 < mode.st_size <= MAX_FILE:
            raise RuntimeError("QA_FILE_SIZE_INVALID_" + str(pk))
        copies.append((real, {"id": pk, "title": str(item.title)[:250],
                              "size": mode.st_size, "sha256": sha(real)}))
    manifest = {"schema": SCHEMA, "site": "mojplaywin.com",
                "originals_are_read_only": True, "replace_live_products": False,
                "products": [row for _, row in copies]}
    validate_manifest(manifest)
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
        raw = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(raw)
        info.mode = 0o600
        archive.addfile(info, io.BytesIO(raw))
        for path, row in copies:
            info = tarfile.TarInfo("product-" + str(row["id"]) + ".bin")
            info.size = row["size"]
            info.mode = 0o600
            with path.open("rb") as stream:
                archive.addfile(info, stream)


def technical_review(path):
    result = {"sha256_verified": True, "archive_crc_pass": False,
              "file_type": "unknown", "issues": []}
    with path.open("rb") as stream:
        magic = stream.read(8)
    if magic.startswith(b"%PDF-"):
        result["file_type"] = "pdf"
        result["issues"].append("PDF_CONTENT_AND_RIGHTS_REQUIRE_REVIEW")
    elif zipfile.is_zipfile(path):
        result["file_type"] = "zip"
        try:
            with zipfile.ZipFile(path) as z:
                infos = z.infolist()
                if not 0 < len(infos) <= 2000:
                    raise ValueError("ZIP_MEMBER_COUNT")
                total = 0
                names = set()
                for i in infos:
                    p = PurePosixPath(i.filename)
                    if (i.filename.startswith("/") or "\\" in i.filename
                            or ".." in p.parts or i.filename in names
                            or (i.external_attr >> 16) & 0o170000 == 0o120000):
                        raise ValueError("ZIP_UNSAFE_MEMBER")
                    names.add(i.filename)
                    total += i.file_size
                    if total > 512 * 1024 * 1024:
                        raise ValueError("ZIP_EXPANSION_LIMIT")
                if z.testzip() is not None:
                    raise ValueError("ZIP_CRC")
                result["archive_crc_pass"] = True
        except (ValueError, RuntimeError, OSError, zipfile.BadZipFile, zlib.error) as exc:
            result["issues"].append("ZIP_INTEGRITY_" + type(exc).__name__)
    else:
        result["issues"].append("FILE_FORMAT_REQUIRES_MANUAL_REVIEW")
    return result


def vps_ingest(root=BASE, input_stream=None):
    root = Path(root)
    private_dir(root)
    if input_stream is None:
        input_stream = sys.stdin.buffer
    with tempfile.TemporaryDirectory(prefix=".incoming-three-", dir=str(root)) as temporary:
        staging = Path(temporary)
        os.chmod(staging, 0o700)
        observed = {}
        with tarfile.open(fileobj=input_stream, mode="r|gz") as archive:
            for member in archive:
                if (member.name not in {"manifest.json", *(f"product-{x}.bin" for x in IDS)}
                        or not member.isfile() or member.name in observed
                        or not 0 < member.size <= MAX_FILE):
                    raise RuntimeError("QA_UNEXPECTED_TAR_MEMBER")
                dest = staging / member.name
                with archive.extractfile(member) as src, dest.open("xb") as dst:
                    shutil.copyfileobj(src, dst, 1048576)
                os.chmod(dest, 0o600)
                observed[member.name] = dest
        if set(observed) != {"manifest.json", *(f"product-{x}.bin" for x in IDS)}:
            raise RuntimeError("QA_INCOMPLETE_TRANSFER")
        if observed["manifest.json"].stat().st_size > 10000:
            raise RuntimeError("QA_MANIFEST_TOO_LARGE")
        rows = validate_manifest(json.loads(observed["manifest.json"].read_text()))
        for row in rows:
            data = observed[f"product-{row['id']}.bin"]
            if data.stat().st_size != row["size"] or sha(data) != row["sha256"]:
                raise RuntimeError("QA_COPY_HASH_MISMATCH_" + str(row["id"]))
        summaries = []
        for row in rows:
            ident, digest = row["id"], row["sha256"]
            src = observed[f"product-{ident}.bin"]
            dest = root / "copies" / str(ident) / (digest + ".bin")
            private_dir(dest.parent)
            if dest.is_symlink():
                raise RuntimeError("QA_DESTINATION_LINK")
            try:
                os.link(src, dest)
            except FileExistsError:
                if dest.is_symlink() or dest.stat().st_size != row["size"] or sha(dest) != digest:
                    raise RuntimeError("QA_EXISTING_COPY_CHANGED")
            report = technical_review(dest)
            request = {"schema": SCHEMA, "site": "mojplaywin.com",
                       "product_id": ident, "product_title": row["title"],
                       "original_sha256": digest, "copy_sha256": sha(dest),
                       "bytes": row["size"], "storefront_unchanged": True,
                       "technical_review": report,
                       "factory_quality_state": "pending_content_rights_and_functional_review",
                       "candidate_rework_allowed": True,
                       "live_replacement_authorized": False,
                       "customer_sales_or_checkout_changed": False,
                       "quality_certified": False}
            receipt = json.dumps(request, ensure_ascii=False, sort_keys=True, indent=2).encode()
            write_once(root / "review-requests" / str(ident) / (digest + ".json"), receipt)
            summaries.append({"product_id": ident, "copy_sha256": digest,
                              "technical_issues": len(report["issues"]),
                              "factory_quality_state": request["factory_quality_state"]})
        print("MPW_LIVE_THREE_QA_PRIVATE_COPIES=" + json.dumps(summaries, sort_keys=True), flush=True)
        return summaries


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["site-export", "vps-ingest"])
    a = p.parse_args()
    if a.mode == "site-export":
        site_export()
    else:
        vps_ingest()


if __name__ == "__main__":
    main()
