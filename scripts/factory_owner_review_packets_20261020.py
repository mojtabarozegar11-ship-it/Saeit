#!/usr/bin/env python3
"""Build authentic, private owner-review packets for factory manufacturing orders.

Strictly NO fabricated passport, review, evidence, product approval or website write.
Existing factory orders and QA results stay unmodified. Python stdlib only.
"""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

ORDER = re.compile(r"^WO-[0-9]{8}\.json$")
SCHEMA = "saeit.factory.owner-review-queue.v1"
PASSPORT_FIELDS = (
    "work_order","title","product_type","version","origin","target_audience",
    "problem_solved","deliverables","file_formats","language","scope",
    "prerequisites","acceptance_criteria","sources","asset_licenses",
    "technical_dependencies","stages_and_owners","resource_budget","sensitivity",
    "producer_id","independent_reviewer_id","human_review_required"
)

def load(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 500000:
        raise RuntimeError("REVIEW_UNTRUSTED_SOURCE")
    obj = json.loads(p.read_text(encoding="utf8"))
    if not isinstance(obj, dict):
        raise RuntimeError("REVIEW_EXPECTED_OBJECT")
    return obj

def safe_dir(path):
    p = Path(path)
    if p.is_symlink():
        raise RuntimeError("REVIEW_SYMLINK_DIRECTORY")
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not p.is_dir() or p.is_symlink():
        raise RuntimeError("REVIEW_NOT_DIRECTORY")
    os.chmod(p, 0o700)
    return p

def serialize(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2)+"\n").encode("utf8")

def save(path, value, immutable=False):
    p = Path(path)
    safe_dir(p.parent)
    raw = serialize(value)
    if p.is_symlink():
        raise RuntimeError("REVIEW_SYMLINK_DESTINATION")
    if p.exists() and immutable:
        if p.read_bytes() != raw:
            raise RuntimeError("REVIEW_IMMUTABLE_PACKET_CHANGED")
        return False
    fd, name = tempfile.mkstemp(prefix=".review-", dir=str(p.parent))
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.chmod(name, 0o600)
        os.replace(name, p)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return True


def inspect_actual_products(root, lifecycle):
    """Proof-carrying private technical prescreen; never release authorization."""
    goods = root/"digital-products"
    output = safe_dir(lifecycle/"product-technical-readiness")
    counts=Counter()
    items=[]
    if not goods.exists():
        folders=[]
    else:
        if goods.is_symlink() or not goods.is_dir():
            raise RuntimeError("REVIEW_PRODUCT_STORAGE_UNSAFE")
        folders=sorted(goods.iterdir())
    if len(folders)>2000:
        raise RuntimeError("REVIEW_PRODUCT_VOLUME_UNSAFE")
    product_id = re.compile(r"^[a-z][a-z0-9_-]{1,80}$")
    sha_re = re.compile(r"^[0-9a-f]{64}$")
    for folder in folders:
        if folder.is_symlink() or not folder.is_dir() or not product_id.fullmatch(folder.name):
            raise RuntimeError("REVIEW_PRODUCT_FOLDER_UNSAFE")
        recipe=folder.name
        manifest=folder/"manufacturing_manifest.json"
        archive=folder/(recipe+"-internal-qa.zip")
        errors=[]
        source_sha=None
        manifest_digest=None
        actual_digest=None
        if not manifest.is_file() or manifest.is_symlink():
            errors.append("MANUFACTURING_MANIFEST_MISSING")
        else:
            manifest_digest=hashlib.sha256(manifest.read_bytes()).hexdigest()
            try:
                m=load(manifest)
                source_sha=m.get("source_sha256")
                if m.get("recipe")!=recipe or m.get("qa_status")!="passed":
                    errors.append("MANUFACTURING_QA_INCOMPLETE")
                if not isinstance(source_sha,str) or not sha_re.fullmatch(source_sha):
                    errors.append("MANUFACTURING_SOURCE_HASH_INVALID")
                expected=m.get("artifact_sha256")
                if not isinstance(expected,str) or not sha_re.fullmatch(expected):
                    errors.append("ARTIFACT_HASH_INVALID")
            except (RuntimeError,ValueError,OSError,TypeError) as exc:
                m={}
                expected=None
                errors.append("MANUFACTURING_MANIFEST_INVALID")
        if archive.is_symlink() or not archive.is_file():
            errors.append("PRODUCT_ARCHIVE_MISSING")
        elif not 100<=archive.stat().st_size<=25*1024*1024:
            errors.append("PRODUCT_ARCHIVE_SIZE_UNSAFE")
        else:
            try:
                import zipfile
                actual_digest=hashlib.sha256(archive.read_bytes()).hexdigest()
                if expected!=actual_digest:
                    errors.append("ARTIFACT_HASH_MISMATCH")
                with zipfile.ZipFile(archive) as z:
                    members=z.infolist()
                    if not members or len(members)>80 or sum(x.file_size for x in members)>100*1024*1024:
                        errors.append("ARCHIVE_LIMIT")
                    else:
                        for member in members:
                            name=member.filename
                            if (member.is_dir() or not name.startswith(recipe+"/")
                                or any(p in ("",".","..") for p in name.split("/"))
                                or "\\\\" in name
                                or (member.external_attr>>16)&0o170000 == 0o120000):
                                errors.append("ARCHIVE_MEMBER_UNSAFE")
                                break
                        if not errors and z.testzip() is not None:
                            errors.append("ARCHIVE_CRC_FAILED")
            except (OSError,ValueError,zipfile.BadZipFile):
                errors.append("ARCHIVE_READ_FAILED")
        good=not errors
        counts["technically_verified" if good else "technical_rework_required"]+=1
        counts["goods_inspected"]+=1
        item={
            "schema":"saeit.factory.private-technical-readiness.v1",
            "recipe":recipe,
            "manufacturing_manifest_sha256":manifest_digest,
            "source_sha256":source_sha if isinstance(source_sha,str) else None,
            "artifact_sha256":actual_digest,
            "technical_archive_integrity_verified":good,
            "technical_blockers":sorted(set(errors)),
            "independent_content_review":False,
            "rights_and_license_review":False,
            "specialist_quality_review":False,
            "owner_publication_approval":False,
            "customer_sale_enabled":False,
            "publication_allowed":False
        }
        h=hashlib.sha256(serialize(item)).hexdigest()
        directory=output/recipe
        save(directory/(h+".json"),item,immutable=True)
        items.append({"recipe":recipe,"evidence_sha256":h,"technical_ok":good,"blockers":item["technical_blockers"]})
    summary={"schema":"saeit.factory.technical-readiness-dashboard.v1",
             "counts":dict(sorted(counts.items())),"items":items,
             "commercial_approval_count":0,"publications":0,"sales":0,
             "requires_independent_review":True}
    save(output/"dashboard.json",summary)
    return summary

def build(root):
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError("REVIEW_FACTORY_ROOT_INVALID")
    inbox = root/"production-instructions"/"orders"
    if not inbox.is_dir() or inbox.is_symlink():
        raise RuntimeError("REVIEW_INSTRUCTIONS_MISSING")
    lifecycle = root/"product-lifecycle"
    if lifecycle.is_symlink():
        raise RuntimeError("REVIEW_LIFECYCLE_SYMLINK")
    queue = safe_dir(lifecycle/"owner-review-queue")
    lock_path = queue/".owner-review.lock"
    if lock_path.is_symlink():
        raise RuntimeError("REVIEW_LOCK_SYMLINK")
    with lock_path.open("a+b") as lock:
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        counts = Counter()
        packets = []
        files = sorted(inbox.iterdir())
        if len(files)>15000:
            raise RuntimeError("REVIEW_UNEXPECTED_ORDER_VOLUME")
        for p in files:
            if p.is_symlink() or not p.is_file() or not ORDER.fullmatch(p.name):
                raise RuntimeError("REVIEW_UNEXPECTED_ORDER_SOURCE")
            item = load(p)
            if item.get("id") != p.stem or item.get("status") not in (
                "issued", "in_engineering", "blocked_rework", "completed_verified"
            ):
                raise RuntimeError("REVIEW_BAD_ORDER_PROVENANCE")
            if item.get("phase")=="research_rework":
                counts["research_waiting_for_real_evidence"] += 1
                continue
            counts["manufacturing_orders"] += 1
            source_sha = hashlib.sha256(p.read_bytes()).hexdigest()
            passport_file = lifecycle/"passports"/(p.stem+".json")
            if passport_file.parent.is_symlink():
                raise RuntimeError("REVIEW_PASSPORT_FOLDER_SYMLINK")
            passport = load(passport_file) if passport_file.exists() else {}
            present = sorted(k for k in PASSPORT_FIELDS if passport.get(k) not in (None,"",[]))
            missing_keys = set(PASSPORT_FIELDS)-set(present)
            if passport:
                if passport.get("schema")!="saeit.factory.product-passport.v1":
                    missing_keys.add("valid_product_passport_schema")
                if passport.get("work_order")!=p.stem:
                    missing_keys.add("work_order")
                if passport.get("human_review_required") is not True:
                    missing_keys.add("human_review_required")
                if passport.get("producer_id")==passport.get("independent_reviewer_id"):
                    missing_keys.add("independent_reviewer_id")
            missing = sorted(missing_keys)
            if not passport:
                counts["missing_passport"] += 1
            elif missing:
                counts["incomplete_passport"] += 1
            else:
                counts["passport_requires_independent_validation"] += 1
            packet = {
                "schema": SCHEMA, "work_order": p.stem,
                "source_instruction_sha256": source_sha,
                "source_state": item["status"],
                "source_phase": str(item.get("phase","unclassified"))[:100],
                "source_origin": str(item.get("origin","unclassified"))[:100],
                "source_subject": str(item.get("subject",""))[:240],
                "passport_fields_present": present,
                "passport_fields_missing": missing,
                "requires_real_sources": True,
                "requires_independent_human_review": True,
                "independent_review_signature_verified": False,
                "manufacturing_approval": False,
                "commercial_release": False,
                "store_publication": False,
                "review_checklist": [
                    "Supply genuine source evidence and verifiable artifact hashes.",
                    "Complete product passport with real owners, formats, licenses and acceptance criteria.",
                    "Perform independent specialist review under the existing signed gate.",
                    "Create only authentic signed stage receipts; never auto-approve.",
                    "Publish only after the separate current release-manifest gate passes."
                ],
            }
            packet_sha = hashlib.sha256(serialize(packet)).hexdigest()
            location = queue/p.stem/(source_sha+"-"+packet_sha+".json")
            if save(location, packet, immutable=True):
                counts["new_private_packets"] += 1
            packets.append({"work_order":p.stem,"source_sha256":source_sha,
                            "packet_sha256":packet_sha,
                            "passport_complete":not missing})
        technical=inspect_actual_products(root,lifecycle)
        summary = {"schema":SCHEMA,"status":"pending_authentic_owner_and_specialist_evidence",
                   "counts":dict(sorted(counts.items())),"packets":packets,
                   "approval_records_written":0,"products_activated":0,
                   "payments_created":0,"sites_contacted":0,
                   "technical_readiness":technical["counts"],
                   "technical_candidates_reviewed":len(technical["items"])}
        save(queue/"dashboard.json", summary)
        return summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private-root", required=True)
    args=p.parse_args()
    outcome=build(args.factory_private_root)
    print("FACTORY_REVIEW_PACKETS="+json.dumps(outcome["counts"],sort_keys=True))
    print("FACTORY_PRIVATE_GOODS_TECHNICAL_READINESS="+json.dumps(outcome["technical_readiness"],sort_keys=True))
    print("FACTORY_REVIEW_NO_AUTO_APPROVAL=PASS")
