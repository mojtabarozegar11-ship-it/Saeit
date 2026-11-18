"""Fail-closed planning for encrypted backups occupying owner VPS storage.

Input: sanitized metadata from a separately authenticated owner SSH Actions job.
This code NEVER takes custody of backup files or keys, invokes shell/network,
selects specific files to delete, declares independent restore, frees a byte,
or permits TRX/payment/production release.

Only mathematical upper bounds are supplied. A 10-GiB backup start gate can
NEVER be satisfied by hypothetical deletions; an OWNER must separately prove
two offsite copies, end-to-end restoration, a retained recoverable original,
the intended exact object identities, and case-specific authorization.
"""
from __future__ import annotations
from typing import Any

GIB=1024**3
MIN_START=10*GIB
SCHEMA="MOJPROP_OWNER_ARCHIVE_SPACE_CLASSES_READONLY_V1"
KINDS=frozenset({
    "mysql_gpg_complete","files_gpg_complete","mysql_manifest","files_manifest",
    "partial_incomplete","other_regular","directories","unsafe_symlinks_or_special"
})
BIG=1<<54


class UnsafeArchiveEvidence(ValueError):
    """Unable to derive capacity from malformed or unauthenticated metadata."""


def integer(value: Any, name: str, maximum: int=BIG) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise UnsafeArchiveEvidence("invalid bounded integer: "+name)
    return value


def boolean(value: Any,name:str) -> bool:
    if type(value) is not bool:
        raise UnsafeArchiveEvidence("invalid boolean: "+name)
    return value


def inspect(snapshot:dict) -> dict:
    if type(snapshot) is not dict or snapshot.get("schema") != SCHEMA:
        raise UnsafeArchiveEvidence("wrong audited snapshot schema")
    for label in ("owner_verified","private_root_valid","all_entries_processed",
                  "ciphertext_content_read","manifest_content_read",
                  "customer_identifiers_printed","archive_names_printed",
                  "production_changed","backup_deleted","backup_moved",
                  "offsite_uploaded","owner_release_authorized"):
        if label not in snapshot:raise UnsafeArchiveEvidence("missing "+label)
        boolean(snapshot[label],label)
    if any(snapshot[k] for k in (
            "ciphertext_content_read","manifest_content_read",
            "customer_identifiers_printed","archive_names_printed",
            "production_changed","backup_deleted","backup_moved",
            "offsite_uploaded","owner_release_authorized")):
        raise UnsafeArchiveEvidence("metadata-only contract violation")
    required=("categories","filesystem_free_bytes",
              "bytes_short_of_10gib_start_gate","entry_count",
              "unreadable_entries_count")
    if any(k not in snapshot for k in required):
        raise UnsafeArchiveEvidence("missing mandatory capacity fields")
    free=integer(snapshot["filesystem_free_bytes"],"filesystem_free_bytes")
    gap=integer(snapshot["bytes_short_of_10gib_start_gate"],"bytes_short_of_10gib_start_gate")
    if gap != max(0,MIN_START-free):
        raise UnsafeArchiveEvidence("10 GiB gate arithmetic mismatch")
    cats=snapshot["categories"]
    if type(cats) is not dict or set(cats)!=KINDS:
        raise UnsafeArchiveEvidence("incomplete or unknown archive class")
    total_files=0
    total_allocated=0
    raw={}
    for k in sorted(KINDS):
        d=cats[k]
        if type(d) is not dict:
            raise UnsafeArchiveEvidence("missing archive row")
        files=integer(d.get("files"),k+".files",2500)
        alloc=integer(d.get("allocated_bytes"),k+".allocated_bytes")
        logical=integer(d.get("logical_bytes"),k+".logical_bytes")
        largest=integer(d.get("largest_allocated_bytes"),k+".largest")
        oldest=d.get("oldest_age_hours")
        youngest=d.get("youngest_age_hours")
        if files==0:
            if any((alloc,logical,largest)) or oldest is not None or youngest is not None:
                raise UnsafeArchiveEvidence("nonempty size for empty archive class")
        else:
            for n,label in ((oldest,"oldest"),(youngest,"youngest")):
                if type(n) not in (float,int) or not 0<=n<=24*365*25:
                    raise UnsafeArchiveEvidence("invalid timestamp "+label)
            if oldest<youngest or largest>alloc:
                raise UnsafeArchiveEvidence("archive allocation consistency failure")
        total_files+=files
        total_allocated+=alloc
        raw[k]={"files":files,"allocated_bytes":alloc,"largest_allocated_bytes":largest}
    entries=integer(snapshot["entry_count"],"entry_count",2501)
    unreadable=integer(snapshot["unreadable_entries_count"],"unreadable_entries_count",2501)
    if total_files+unreadable!=entries and snapshot["all_entries_processed"]:
        raise UnsafeArchiveEvidence("reported rows do not cover bounded inventory")
    if snapshot["all_entries_processed"] and (unreadable or entries>2500):
        raise UnsafeArchiveEvidence("inconsistent completeness flag")
    classified=bool(snapshot["owner_verified"] and snapshot["private_root_valid"]
                    and snapshot["all_entries_processed"] and not unreadable)
    old_complete=raw["mysql_gpg_complete"]["files"]>0 and raw["files_gpg_complete"]["files"]>0
    potential=(
        raw["mysql_gpg_complete"]["allocated_bytes"]
        +raw["files_gpg_complete"]["allocated_bytes"]
        +raw["partial_incomplete"]["allocated_bytes"]
        +raw["other_regular"]["allocated_bytes"])
    return {
        "schema":"MOJPROP_ARCHIVE_CAPACITY_DECISION_NO_DELETE_V1",
        "snapshot_independently_authenticated_by_this_pure_script":False,
        "metadata_classification_complete_claim":classified,
        "existing_mysql_and_files_ciphertext_candidates_observed":old_complete,
        "owner_vps_current_free_bytes":free,
        "mandatory_10gib_before_start_bytes":MIN_START,
        "bytes_still_missing_without_any_changes":gap,
        "allocated_bytes_of_all_classified_direct_regular_files_NOT_RECLAIMABLE_PROOF":potential,
        "private_archive_classified_allocation_bytes":total_allocated,
        "files_in_classes":total_files,
        "classes":raw,
        "sufficient_fresh_backup_capacity_without_changes":free>=MIN_START,
        "existing_backups_independently_restored":False,
        "two_independent_verified_offsite_copies":False,
        "archive_cleanup_case_specific_owner_authorization":False,
        "archive_automatically_safe_to_remove_count":0,
        "bytes_safe_to_delete_now":0,
        "cleanup_operation_performed":False,
        "backup_operation_performed":False,
        "release_or_payment_permitted":False,
        "next_step":"secure_verified_offsite_then_restoration_then_owner_decision"
           if potential>=gap else "find_additional_private_capacity_without_deletion",
    }
