#!/usr/bin/env python3
"""VPS-local order-free product delivery to cPanel's private inbox over pinned SSH.

No GitHub or ChatGPT dependency at runtime. No payment, Django writes,
public product activation, external commerce or customer orders.
"""
import argparse
import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path
import re
import subprocess
import sys
import zipfile

HOST = "zohal.pws-dns.net"
USER = "zomorod2"
PORT = 1396
HOST_KEY_SHA256 = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"
INBOX = "/home/zomorod2/.saeit-factory-inbox"
RECEIVER = INBOX + "/bin/store_receiver.py"
SLUG = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_BUNDLE = 25 * 1024 * 1024


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_source(manifest_path, archive_path, recipe):
    if not SLUG.fullmatch(recipe):
        raise ValueError("RECIPE_NAME_INVALID")
    if any(p.is_symlink() or not p.is_file() for p in (manifest_path, archive_path)):
        raise ValueError("RECIPE_PATH_UNSAFE")
    if (archive_path.stat().st_size <= 0 or archive_path.stat().st_size > MAX_BUNDLE
            or manifest_path.stat().st_size > 100000):
        raise ValueError("PACKAGE_SIZE_UNSAFE")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("PACKAGE_MANIFEST_INVALID_JSON") from exc
    if not isinstance(manifest, dict):
        raise ValueError("PACKAGE_MANIFEST_INVALID")
    digest = manifest.get("artifact_sha256")
    if not isinstance(digest, str) or not SHA.fullmatch(digest) or digest != sha256(archive_path):
        raise ValueError("PACKAGE_SHA256_MISMATCH")
    if (manifest.get("recipe") != recipe or manifest.get("qa_status") != "passed"
        or manifest.get("commercial_status") != "private_internal_qa_pass_not_published"
        or manifest.get("owner_publication_approval") is not False
        or manifest.get("public_listing_enabled") is not False
        or manifest.get("price") is not None):
        raise ValueError("PACKAGE_NOT_PRIVATE_QA_PASSED")
    # Validate actual ZIP bytes; a matching SHA and "passed" JSON is insufficient.
    try:
        with zipfile.ZipFile(archive_path) as bundle:
            members = bundle.infolist()
            if not 0 < len(members) <= 256 or sum(i.file_size for i in members) > 100 * 1024 * 1024:
                raise ValueError("PACKAGE_ARCHIVE_EXPANSION_UNSAFE")
            expected = manifest.get("files")
            if (not isinstance(expected, list) or len(expected)!=len(members)
                    or len(set(expected))!=len(members)
                    or not all(isinstance(v,str) and 0<len(v)<=240 for v in expected)
                    or {recipe + "/" + v for v in expected} != {v.filename for v in members}
                    or len({v.filename for v in members}) != len(members)):
                raise ValueError("PACKAGE_ARCHIVE_MANIFEST_MISMATCH")
            if any(i.filename.startswith("/") or ".." in Path(i.filename).parts or
                   "\\" in i.filename for i in members):
                raise ValueError("PACKAGE_ARCHIVE_MEMBER_UNSAFE")
            if bundle.testzip() is not None:
                raise ValueError("PACKAGE_ARCHIVE_CORRUPT")
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("PACKAGE_ARCHIVE_INVALID") from exc
    # The last technically-good ZIP may still exist after a new source
    # revision fails. Never ship that stale package while a defect is open.
    # The private receiver is not a public storefront, but stale QA must
    # still fail closed before any transfer.
    ledger = manifest_path.parents[2] / "qa-rework" / recipe / "ledger.json"
    if ledger.is_symlink():
        raise ValueError("PRIVATE_REWORK_LEDGER_UNSAFE")
    if ledger.is_file():
        try:
            state = json.loads(ledger.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError("PRIVATE_REWORK_LEDGER_INVALID") from exc
        if not isinstance(state, dict) or state.get("schema") != "saeit.factory.qa-rework.v1":
            raise ValueError("PRIVATE_REWORK_LEDGER_UNVERIFIED")
        status = state.get("current_status")
        if status != "technical_qa_pass_only_owner_and_content_review_pending":
            raise ValueError("PRIVATE_PRODUCT_BLOCKED_FOR_REWORK")
        history = state.get("history")
        if (not isinstance(history, list) or not history or
                not isinstance(history[-1], dict) or
                history[-1].get("status") != "technically_recovered"):
            raise ValueError("PRIVATE_REWORK_RECOVERY_UNVERIFIED")
    return digest


def host_ssh_options(key, known):
    if any(p.is_symlink() or not p.is_file() for p in (key, known)):
        raise ValueError("SSH_IDENTITY_OR_PIN_MISSING")
    if key.stat().st_mode & 0o077:
        raise ValueError("SSH_KEY_PERMISSIONS_UNSAFE")
    checked = subprocess.run(["ssh-keygen", "-lf", str(known), "-E", "sha256"],
                             capture_output=True, text=True, timeout=8, check=True)
    fingerprints = {line.split()[1] for line in checked.stdout.splitlines()
                    if len(line.split()) > 1}
    if fingerprints != {HOST_KEY_SHA256}:
        raise ValueError("CPANEL_HOST_PIN_MISMATCH")
    return ["-i", str(key), "-o", "StrictHostKeyChecking=yes", "-o", "BatchMode=yes",
            "-o", "IdentitiesOnly=yes", "-o", "UserKnownHostsFile=" + str(known),
            "-o", "ConnectTimeout=12"]


SAFE_STAGES = frozenset({
    "status", "prepare", "upload_archive", "upload_manifest", "finalize", "receipt",
    "consumer_status", "consumer_prepare", "consumer_upload_archive",
    "consumer_upload_manifest", "consumer_finalize",
})


def call(command, *, allowed=(0,), timeout=40, stage="unknown"):
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if completed.returncode not in allowed:
        # A receiver may emit a single documented, fixed validation code.
        # Never print arbitrary remote stderr, paths, command arguments or keys.
        if stage == "finalize" and completed.returncode == 1:
            safe_class = re.search(
                r"(?m)^STORE_RECEIVER_ERROR=(ValueError|JSONDecodeError|BadZipFile|"
                r"OSError|FileNotFoundError|PermissionError)$",
                completed.stderr or "",
            )
            if safe_class:
                print("FACTORY_STORE_RECEIVER_ERROR_CLASS=" + safe_class.group(1),
                      file=sys.stderr)
            found = re.search(r"(?m)^STORE_RECEIVER_SAFE_REASON=([A-Z0-9_]{3,80})$",
                              completed.stderr or "")
            allowed_reasons = {
                "INBOX_SYMLINK_REJECTED", "INBOX_DIRECTORY_INVALID",
                "INVALID_RECIPE_OR_DIGEST", "SYMLINK_IN_UPLOAD",
                "INCOMPLETE_UPLOAD", "INVALID_ARCHIVE_SIZE",
                "MANIFEST_TOO_LARGE", "BAD_MANIFEST",
                "MANIFEST_IDENTITY_MISMATCH", "UNSAFE_OR_UNREVIEWED_MANIFEST",
                "SHA256_MISMATCH", "F34_EVIDENCE_CONTRACT_INVALID",
                "F34_EXACT_ICON_PACKAGE_INVALID", "ARCHIVE_FILE_COUNT_INVALID",
                "ARCHIVE_EXPANSION_LIMIT", "UNSAFE_ARCHIVE_MEMBER",
                "CORRUPT_ARCHIVE",
            }
            if found and found.group(1) in allowed_reasons:
                print("FACTORY_STORE_RECEIVER_REJECTION=" + found.group(1),
                      file=sys.stderr)
        safe_stage = stage if stage in SAFE_STAGES else "unknown"
        raise RuntimeError("PRIVATE_DELIVERY_" + safe_stage.upper()
                           + "_RC_" + str(completed.returncode))
    return completed


def deliver(recipe, source, ssh_options, *, dry_run=False):
    manifest = source / recipe / "manufacturing_manifest.json"
    archive = source / recipe / (recipe + "-internal-qa.zip")
    digest = verify_source(manifest, archive, recipe)
    remote = USER + "@" + HOST
    receiver_args = ["python3", RECEIVER]
    target = INBOX + "/incoming/" + recipe + "/" + digest
    ssh_base = ["ssh", "-p", str(PORT)] + ssh_options + [remote]
    if dry_run:
        return {"recipe": recipe, "digest": digest, "status": "dry_run_private_only"}
    check = call(ssh_base + [" ".join(receiver_args + [
        "status", recipe, digest, "--root", INBOX])], allowed=(0, 1), stage="status")
    if check.returncode == 0:
        return {"recipe": recipe, "digest": digest, "status": "already_received"}
    call(ssh_base + [" ".join(receiver_args + [
        "prepare", recipe, digest, "--root", INBOX])], stage="prepare")
    for local, suffix in ((archive, ".zip.partial"), (manifest, ".json.partial")):
        scp = ["scp", "-P", str(PORT)] + ssh_options + [
            str(local), remote + ":" + target + suffix]
        call(scp, timeout=65, stage="upload_archive" if local == archive else "upload_manifest")
    call(ssh_base + [" ".join(receiver_args + [
        "finalize", recipe, digest, "--root", INBOX])], stage="finalize")
    receipt = call(ssh_base + [" ".join(receiver_args + [
        "status", recipe, digest, "--root", INBOX])], stage="receipt")
    if "STORE_PRIVATE_RECEIPT_VERIFIED" not in receipt.stdout:
        raise RuntimeError("STORE_RECEIPT_NOT_VERIFIED")
    return {"recipe": recipe, "digest": digest, "status": "received_private"}



def verify_consumer_source(root, recipe, version):
    """Read only a real buyer-use archive tied to the exact previous QA ZIP."""
    if not SLUG.fullmatch(recipe) or not SHA.fullmatch(version):
        raise ValueError("CONSUMER_PRODUCT_VERSION_INVALID")
    root=Path(root).expanduser().resolve()
    files=root/"customer-packs"/recipe/version
    if files.is_symlink() or not files.is_dir():
        raise ValueError("CONSUMER_PACKAGE_NOT_AVAILABLE")
    candidate=files/"candidate_manifest.json"
    archive=files/"customer-package.zip"
    source=root/"digital-products"/recipe/"manufacturing_manifest.json"
    original=root/"digital-products"/recipe/(recipe+"-internal-qa.zip")
    for item in (candidate,archive,source,original):
        if item.is_symlink() or not item.is_file():
            raise ValueError("CONSUMER_SOURCE_UNSAFE")
    if candidate.stat().st_size>100000 or not 0<archive.stat().st_size<=MAX_BUNDLE:
        raise ValueError("CONSUMER_SIZE_REJECTED")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
        manifest = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("CONSUMER_MANIFEST_INVALID_JSON") from exc
    # Valid JSON may be a list, string, number or null, none of which has
    # the required provenance fields. Fail closed before reading .get().
    if not isinstance(doc, dict) or not isinstance(manifest, dict):
        raise ValueError("CONSUMER_MANIFEST_NOT_OBJECT")
    if (manifest.get("source_sha256")!=version
            or manifest.get("recipe")!=recipe
            or manifest.get("qa_status")!="passed"
            or manifest.get("public_listing_enabled") is not False
            or sha256(original)!=manifest.get("artifact_sha256")
            or doc.get("schema")!="saeit.factory.consumer-package.v1"
            or doc.get("product_id")!=recipe
            or doc.get("factory_source_sha256")!=version
            or doc.get("factory_internal_zip_sha256")!=manifest.get("artifact_sha256")
            or doc.get("technical_buyer_package_verified") is not True
            or doc.get("consumer_cli_smoke_examples_passed")!=2
            or doc.get("commercial_release") is not False
            or doc.get("public_download_allowed") is not False
            or doc.get("eligible_for_commercial_listing") is not False
            or doc.get("independent_domain_review_completed") is not False
            or doc.get("rights_and_license_review_completed") is not False
            or doc.get("price") is not None
            or doc.get("package_sha256")!=sha256(archive)
            or doc.get("package_bytes")!=archive.stat().st_size):
        raise ValueError("CONSUMER_PACKAGE_PROVENANCE_OR_POLICY_INVALID")
    with zipfile.ZipFile(str(archive)) as zipped:
        names=zipped.namelist()
        needed={"guide/START_HERE.md","product/calculator.py","product/example_inputs.json",
                "qa/SHA256SUMS.txt","license/REVIEW_REQUIRED.txt"}
        if len(names)>80 or not needed.issubset(set(names)) or zipped.testzip() is not None:
            raise ValueError("CONSUMER_ZIP_QA_NOT_PASSED")
        if b"NOT LICENSED FOR PUBLIC RESALE" not in zipped.read("license/REVIEW_REQUIRED.txt"):
            raise ValueError("CONSUMER_RIGHTS_HOLD_INVALID")
        for line in zipped.read("qa/SHA256SUMS.txt").decode("utf8").splitlines():
            digest,separator,name=line.partition("  ")
            if not separator or not SHA.fullmatch(digest) or name not in names:
                raise ValueError("CONSUMER_MEMBER_SUM_MISSING")
            if hashlib.sha256(zipped.read(name)).hexdigest()!=digest:
                raise ValueError("CONSUMER_MEMBER_SUM_CHANGED")
    return candidate,archive,doc


def deliver_consumer(recipe, root, version, ssh_options, *, dry_run=False):
    candidate,archive,meta=verify_consumer_source(root,recipe,version)
    if dry_run:
        return {"recipe":recipe,"version":version,"status":"dry_run_private_consumer",
                "package_sha256":meta["package_sha256"]}
    remote=USER+"@"+HOST
    base=["ssh","-p",str(PORT)]+ssh_options+[remote]
    def received():
        status=call(base+[" ".join(["python3",RECEIVER,
            "consumer-status",recipe,version,"--root",INBOX])],allowed=(0,1),stage="consumer_status")
        return status.returncode==0 and "STORE_CONSUMER_PRIVATE_RECEIPT_VERIFIED" in status.stdout
    if received():
        return {"recipe":recipe,"version":version,"status":"already_received_customer",
                "package_sha256":meta["package_sha256"]}
    call(base+[" ".join(["python3",RECEIVER,
        "consumer-prepare",recipe,version,"--root",INBOX])],stage="consumer_prepare")
    target=INBOX+"/incoming/consumer/"+recipe+"/"+version+"/"
    for local,part in ((archive,"customer-package.zip.partial"),
                       (candidate,"candidate_manifest.json.partial")):
        call(["scp","-P",str(PORT)]+ssh_options+[str(local),remote+":"+target+part],
             timeout=65,stage="consumer_upload_archive" if local == archive
             else "consumer_upload_manifest")
    call(base+[" ".join(["python3",RECEIVER,
        "consumer-finalize",recipe,version,"--root",INBOX])],stage="consumer_finalize")
    if not received():raise RuntimeError("CONSUMER_SITE_SHA_RECEIPT_NOT_VERIFIED")
    return {"recipe":recipe,"version":version,"status":"received_private_customer",
            "package_sha256":meta["package_sha256"]}


CURSOR_SCHEMA = "saeit.factory.store-private-delivery-cursor.v1"


def rotate_recipes(products, last_recipe, limit):
    """Deterministic rotation: new recipe names and later families get turns."""
    ordered = sorted(set(products))
    if last_recipe:
        ordered = [name for name in ordered if name > last_recipe] + [
            name for name in ordered if name <= last_recipe
        ]
    return ordered[:limit]


def read_cursor(path):
    if path.is_symlink():
        raise ValueError("STORE_CURSOR_SYMLINK_UNSAFE")
    if not path.exists():
        return ""
    if not path.is_file() or path.stat().st_size > 4096:
        raise ValueError("STORE_CURSOR_INVALID_FILE")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise ValueError("STORE_CURSOR_CORRUPTED") from error
    if (not isinstance(record, dict) or record.get("schema") != CURSOR_SCHEMA
            or not isinstance(record.get("last_recipe"), str)
            or not SLUG.fullmatch(record["last_recipe"])):
        raise ValueError("STORE_CURSOR_SCHEMA_INVALID")
    return record["last_recipe"]


def save_cursor(path, recipe):
    if path.is_symlink() or not SLUG.fullmatch(recipe):
        raise ValueError("STORE_CURSOR_UNSAFE")
    payload = json.dumps({"schema": CURSOR_SCHEMA, "last_recipe": recipe},
                         sort_keys=True) + "\n"
    fd, temp = tempfile.mkstemp(prefix=".store-send-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def sync(source, key, known, *, limit=3, dry_run=False):
    if limit < 1 or limit > 20:
        raise ValueError("LIMIT_OUT_OF_RANGE")
    root = Path(source).expanduser().resolve()
    if not root.is_dir() or root.parent.is_symlink():
        raise ValueError("FACTORY_PRODUCTS_MISSING_OR_UNSAFE")
    options = host_ssh_options(Path(key).expanduser(), Path(known).expanduser())
    products = sorted(p.name for p in root.iterdir()
                      if p.is_dir() and not p.is_symlink() and SLUG.fullmatch(p.name))
    if not products:
        return []
    cursor_path = root.parent / "store-send-cursor.json"
    lock_path = root.parent / ".store-send-cursor.lock"
    if lock_path.is_symlink():
        raise ValueError("STORE_CURSOR_LOCK_SYMLINK_UNSAFE")
    with lock_path.open("a+b") as lock:
        os.fchmod(lock.fileno(), 0o600)
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("STORE_SYNC_ALREADY_RUNNING") from error
        # Scan every recipe at most once per tick so one invalid QA package
        # cannot starve the next healthy three. Failed packages remain blocked
        # and eligible for retry after their source is repaired.
        selected = rotate_recipes(products, read_cursor(cursor_path), len(products))
        results = []
        eligible = 0
        for recipe in selected:
            manifest = root / recipe / "manufacturing_manifest.json"
            archive = root / recipe / (recipe + "-internal-qa.zip")
            try:
                verify_source(manifest, archive, recipe)
            except (ValueError, OSError) as error:
                # Only product-local source validation may be isolated. Remote
                # delivery/receipt errors still abort without advancing cursor.
                results.append({"recipe": recipe, "status": "blocked_private_qa",
                                "failure_type": type(error).__name__})
                continue
            result = deliver(recipe, root, options, dry_run=dry_run)
            results.append(result)
            eligible += 1
            if not dry_run:
                save_cursor(cursor_path, recipe)
            if eligible >= limit:
                break
        return results


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--products", required=True)
    parser.add_argument("--ssh-key", required=True)
    parser.add_argument("--known-hosts", required=True)
    parser.add_argument("--max-products", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    results = sync(args.products, args.ssh_key, args.known_hosts,
                   limit=args.max_products, dry_run=args.dry_run)
    for item in results:
        print("FACTORY_STORE_PRODUCT=" + item["recipe"])
        print("FACTORY_STORE_DELIVERY=" + item["status"])
    print("FACTORY_STORE_TRANSFER_COUNT=" + str(sum(
        item["status"] == "received_private" for item in results)))
    print("FACTORY_STORE_RECEIPT_VERIFIED_COUNT=" + str(sum(
        item["status"] in ("received_private", "already_received") for item in results)))
    print("FACTORY_STORE_ALREADY_RECEIVED_COUNT=" + str(sum(
        item["status"] == "already_received" for item in results)))
    print("FACTORY_STORE_QA_BLOCKED_COUNT=" + str(sum(
        item["status"] == "blocked_private_qa" for item in results)))
    print("FACTORY_STORE_DRY_RUN_VERIFIED_COUNT=" + str(sum(
        item["status"] == "dry_run_private_only" for item in results)))
    print("FACTORY_STORE_ORDERS_REQUIRED=false")
    print("FACTORY_STORE_PUBLIC_LISTING_ENABLED=false")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("FACTORY_STORE_DELIVERY_FAILED=" + type(exc).__name__, file=sys.stderr)
        detail = str(exc) if isinstance(exc, RuntimeError) else ""
        # Only a fixed step name and numeric exit code may leave the server.
        if (re.fullmatch(r"PRIVATE_DELIVERY_[A-Z_]+_RC_-?[0-9]{1,3}", detail)
                or detail in ("STORE_RECEIPT_NOT_VERIFIED",
                              "CONSUMER_SITE_SHA_RECEIPT_NOT_VERIFIED",
                              "STORE_SYNC_ALREADY_RUNNING")):
            print("FACTORY_STORE_SAFE_FAILURE=" + detail, file=sys.stderr)
        sys.exit(1)
