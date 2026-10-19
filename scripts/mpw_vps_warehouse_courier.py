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
import fcntl
import hashlib
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

TENANT = "mojplaywin-main"
SCHEMA = "mpw.factory.warehouse-courier.v1"
RETURN_SCHEMA = "mpw.factory.return-to-stage1.v1"
VPS = Path.home() / "factory-runtime/private/autonomous-product-cycle"
PANEL = Path("/home/zomorod2/.private_mojplaywin_main_agents")
DEST = PANEL / "evolution_runtime_20261018/warehouse_courier"
RECIPE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
MAX_ZIP = 25 * 1024 * 1024
MAX_PACKAGE = 110 * 1024 * 1024
MAX_ITEMS = 50
MAX_FILES = 101
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


def stock_records(root):
    clean_dir(root)
    finished = root / "production-warehouse/finished"
    clean_dir(finished)
    result = []
    for product in sorted(finished.iterdir()):
        require(not product.is_symlink() and product.is_dir()
                and RECIPE.fullmatch(product.name), "WAREHOUSE_PRODUCT_PATH_INVALID")
        for version in sorted(product.iterdir()):
            require(not version.is_symlink() and version.is_dir()
                    and SHA.fullmatch(version.name), "WAREHOUSE_VERSION_PATH_INVALID")
            manifest_path = version / "warehouse_manifest.json"
            artifact_path = version / "product.zip"
            manifest = json_file(manifest_path, 100_000)
            require(artifact_path.is_file() and not artifact_path.is_symlink()
                    and artifact_path.stat().st_size <= MAX_ZIP, "WAREHOUSE_ZIP_INVALID")
            raw = artifact_path.read_bytes()
            verify_stock(manifest, product.name, version.name, raw)
            result.append((product.name, version.name, manifest, raw))
            require(len(result) <= MAX_ITEMS, "WAREHOUSE_BATCH_LIMIT")
    return result


def add_tar(tar, name, raw):
    require(len(raw) <= MAX_ZIP, "ARCHIVE_MEMBER_TOO_LARGE")
    info = tarfile.TarInfo(name)
    info.size = len(raw)
    info.mode = 0o600
    info.mtime = 0
    tar.addfile(info, io.BytesIO(raw))


def export_factory(root=VPS):
    records = stock_records(Path(root))
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as tar:
        index = {"schema": SCHEMA, "tenant": TENANT, "created_utc": stamp(),
                 "inventory_count": len(records),
                 "items": [{"product_id":p, "version":v,
                            "artifact_sha256":m["artifact_sha256"],
                            "bytes":len(blob)} for p,v,m,blob in records]}
        add_tar(tar, "index.json", json_blob(index))
        for product, version, manifest, raw in records:
            name = "items/" + product + "/" + version + "/"
            add_tar(tar, name + "manifest.json", json_blob(manifest))
            add_tar(tar, name + "product.zip", raw)
    value = stream.getvalue()
    require(len(value) <= MAX_PACKAGE, "WAREHOUSE_TRANSFER_TOO_LARGE")
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
        products.append((product, version, manifest, blobs[base+"product.zip"]))
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
    rows = []
    for product, version, manifest, content in products:
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
        # This independent QA does NOT invent a content, licensing or owner
        # approval. Missing commercial verification returns to stage one.
        issues = list(ISSUES)
        qa = {"schema": SCHEMA,"tenant":TENANT,"product_id":product,
              "version":version,"artifact_sha256":manifest["artifact_sha256"],
              "technical_zip_verified":True,"commercial_approved":False,
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
              "duplicate_versions_skipped":previous,"quality_approved":0,
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


def main():
    require(len(sys.argv)==2, "COURIER_MODE_REQUIRED")
    mode=sys.argv[1]
    if mode=="vps-export":
        sys.stdout.buffer.write(export_factory())
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
    else:
        raise RuntimeError("INVALID_COURIER_MODE")


if __name__=="__main__":
    main()
