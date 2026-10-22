"""Fail-closed private six-family native QA evidence gateway.

Read only. An authenticated AgentTask must invoke this through ToolGateway.
Never infers physical tests, human certification, product launch or revenue.
"""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ACTION = "factory_native_review"
REVIEW_SCHEMA = "saeit.factory.six-native-independent-technical-review.v1"
FAMILIES = ("F12", "F13", "F14", "F16", "F17", "F26")
COUNT = {"F12":2, "F13":1, "F14":2, "F16":2, "F17":1, "F26":48}
RUN = re.compile(r"^[0-9]{5,18}-[0-9]{1,3}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
NAME = re.compile(r"^[A-Za-z0-9_.-]{3,96}$")

def digest(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("NATIVE_AGENT_FILE_MISSING_OR_SYMLINK")
    h = hashlib.sha256()
    with path.open("rb") as file:
        for data in iter(lambda: file.read(131072), b""):
            h.update(data)
    return h.hexdigest()

def read_json(path, max_bytes=160000):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError("NATIVE_AGENT_RECEIPT_UNSAFE")
    result=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("NATIVE_AGENT_OBJECT_REQUIRED")
    return result

def private_root(value):
    root=Path(value).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("NATIVE_AGENT_PRIVATE_ROOT_UNSAFE")
    return root

def snapshot(root, run):
    if not isinstance(run,str) or not RUN.fullmatch(run):
        raise ValueError("NATIVE_AGENT_INVALID_RUN")
    private=private_root(root)
    review=private/"quality-excellence"/"six-native-rework"/run
    native=private/"native-candidate-evidence"/run
    if any(p.is_symlink() or not p.is_dir() for p in (review,native)):
        raise ValueError("NATIVE_AGENT_UNVERIFIED_RUN")
    overview=review/"review.json"
    source=native/"verified-six-private-native.json"
    r=read_json(overview)
    a=read_json(source)
    if (r.get("schema")!=REVIEW_SCHEMA or r.get("source_run")!=run
            or r.get("reviewed_families")!=6
            or r.get("verified_native_candidate_files")!=56
            or r.get("independent_machine_review_performed") is not True
            or r.get("completed_professional_quality_1000_certifications")!=0
            or r.get("commercial_release_authorized") is not False
            or r.get("source_aggregate_sha256")!=digest(source)
            or a.get("schema")!="saeit.factory.native-six-vps-aggregate.v1"
            or a.get("six_families_verified")!=6
            or a.get("candidate_native_file_count")!=56
            or a.get("private_only") is not True
            or a.get("production_release_authorized") is not False):
        raise ValueError("NATIVE_AGENT_INDEPENDENT_EVIDENCE_INVALID")
    rows=r.get("families")
    arows=a.get("files")
    if (not isinstance(rows,list) or not isinstance(arows,list)
            or len(rows)!=6 or len(arows)!=6
            or {i.get("family_id") for i in rows}!=set(FAMILIES)
            or {i.get("family") for i in arows}!=set(FAMILIES)):
        raise ValueError("NATIVE_AGENT_SIX_IDENTITIES_UNVERIFIED")
    for family in FAMILIES:
        found=next(i for i in rows if i["family_id"]==family)
        recorded=read_json(review/(family+".json"))
        agg=next(i for i in arows if i["family"]==family)
        if (recorded!=found or recorded.get("family_id")!=family
                or found.get("technical_native_artifact_integrity_verified") is not True
                or found.get("independent_professional_approval") is not False
                or found.get("quality_1000_certified") is not False
                or found.get("commercial_release_authorized") is not False
                or found.get("artifact_sha256")!=agg.get("archive_sha256")
                or found.get("format_artifact_count")!=COUNT[family]
                or agg.get("verified_on_vps") is not True
                or agg.get("native_candidate_files")!=COUNT[family]):
            raise ValueError("NATIVE_AGENT_FAMILY_RECEIPT_MISMATCH")
    return r

def latest_snapshot(root):
    base=private_root(root)/"quality-excellence"/"six-native-rework"
    if base.is_symlink() or not base.is_dir():
        raise ValueError("NATIVE_AGENT_REVIEW_QUEUE_MISSING")
    completed=[]
    for entry in base.iterdir():
        if entry.is_symlink() or not entry.is_dir() or not RUN.fullmatch(entry.name):
            continue
        if not (entry/"review.json").is_file():
            continue
        completed.append(entry.name)
    if not completed:
        raise ValueError("NATIVE_AGENT_NO_COMPLETE_REVIEWS")
    for run in sorted(completed,key=lambda i:tuple(map(int,i.split("-"))),reverse=True):
        try:
            snapshot(root,run)
        except (ValueError,KeyError,TypeError,FileNotFoundError):
            continue
        return run
    raise ValueError("NATIVE_AGENT_NO_VALID_REVIEW_SNAPSHOT")

def inspect_family(root, payload):
    if not isinstance(payload,dict):
        raise ValueError("NATIVE_AGENT_PAYLOAD_REQUIRED")
    family=payload.get("family")
    run=payload.get("source_run")
    report_sha=payload.get("review_sha256")
    row_sha=payload.get("family_receipt_sha256")
    if (family not in FAMILIES or not isinstance(run,str) or not RUN.fullmatch(run)
            or not isinstance(report_sha,str) or not SHA.fullmatch(report_sha)
            or not isinstance(row_sha,str) or not SHA.fullmatch(row_sha)):
        raise ValueError("NATIVE_AGENT_INVALID_BOUND_IDENTITY")
    r=snapshot(root,run)
    folder=private_root(root)/"quality-excellence"/"six-native-rework"/run
    if (digest(folder/"review.json")!=report_sha
            or digest(folder/(family+".json"))!=row_sha):
        raise ValueError("NATIVE_AGENT_SOURCE_VERSION_CHANGED")
    row=next(x for x in r["families"] if x["family_id"]==family)
    native=private_root(root)/"native-candidate-evidence"/run/family
    rc=read_json(native/"technical-native-receipt.json")
    if (rc.get("schema")!="saeit.factory.private-six-native-candidate.v1"
            or rc.get("family")!=family or rc.get("archive_sha256")!=row["artifact_sha256"]
            or rc.get("commercial_release") is not False
            or rc.get("quality_1000_certified") is not False
            or rc.get("independent_specialist_review_verified") is not False):
        raise ValueError("NATIVE_AGENT_PRODUCT_RECEIPT_POLICY_FAIL")
    archive=native/"technical-native-candidate.zip"
    if archive.stat().st_size>220000000 or digest(archive)!=row["artifact_sha256"]:
        raise ValueError("NATIVE_AGENT_ARCHIVE_HASH_FAIL")
    files=rc.get("archive_members_sha256")
    if not isinstance(files,dict) or len(files)>60 or not files:
        raise ValueError("NATIVE_AGENT_FILES_UNVERIFIED")
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if (len(names)!=len(files) or set(names)!=set(files)
                or z.testzip() is not None
                or sum(info.file_size for info in z.infolist())>300000000):
            raise ValueError("NATIVE_AGENT_ARCHIVE_ENTRIES_INVALID")
        for name,hash_ in files.items():
            if (not NAME.fullmatch(name) or not isinstance(hash_,str)
                    or not SHA.fullmatch(hash_)
                    or hashlib.sha256(z.read(name)).hexdigest()!=hash_):
                raise ValueError("NATIVE_AGENT_MEMBER_HASH_FAIL")
    pending=row.get("unverified_specialist_or_physical_gates")
    defects=row.get("remediable_source_defects")
    if (not isinstance(pending,list) or not pending
            or not isinstance(defects,list)
            or not all(isinstance(v,str) and len(v)<110 for v in pending+defects)):
        raise ValueError("NATIVE_AGENT_GATE_STATUS_INVALID")
    return {
        "verified_effect":True,
        "action_performed":"Authenticated master task independently reopened the native family candidate and validated immutable machine QA receipts.",
        "family":family,
        "source_run":run,
        "source_review_sha256":report_sha,
        "family_receipt_sha256":row_sha,
        "artifact_sha256":row["artifact_sha256"],
        "native_files_verified":COUNT[family],
        "source_defects":defects,
        "pending_external_specialist_gates":pending,
        "next_action":("specialist_source_rework" if defects
                       else "collect_independent_device_and_professional_evidence"),
        "master_verified_task_execution":True,
        "quality_1000_certified":False,
        "commercial_release":False,
        "website_mutations":0
    }
