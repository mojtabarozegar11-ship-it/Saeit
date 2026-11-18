"""Technical completion receipt for BOTH MySQL+scoped-files encrypted kind streams.

This NEVER means a fresh production backup or actual SQL/media restoration:
a separate, independently reviewed source snapshot and offsite escrow/replay
must prove the DB belongs to the effective Passenger app and all media exists.
All reads/writes are through injected private stores, not VPS disk/OAuth here.
An upload of one kind cannot create a complete-pair receipt.
"""
from __future__ import annotations
import json
import re
import hashlib

from scripts import mojprop_direct_dual_offsite_stream_core_20261118 as core

PAIR_SCHEMA="mojprop-dual-offsite-two-kind-technical-receipt.v1"
SHA40=re.compile(r"[0-9a-f]{40}\Z")


def _load_manifest(sinks,base,kind,pubsha):
    key=base+kind+"/manifest.json"
    values=[s.read_exact(key,core.MAX_MANIFEST+1) for s in sinks]
    if any(type(v) is not bytes or not v or len(v)>core.MAX_MANIFEST for v in values):
        raise core.DualOffsiteDenied("PAIR_KIND_MANIFEST_MISSING_OR_TOO_LONG")
    if values[0]!=values[1]:
        raise core.DualOffsiteDenied("PAIR_CLOUD_KIND_MANIFEST_DISAGREES")
    try:
        payload=json.loads(values[0])
    except (UnicodeError,ValueError) as exc:
        raise core.DualOffsiteDenied("PAIR_KIND_MANIFEST_MALFORMED") from exc
    if (type(payload) is not dict or payload.get("schema")!=core.SCHEMA or
        payload.get("kind")!=kind or
        payload.get("recipient_public_key_sha256")!=pubsha or
        payload.get("set_id")!=base.split("/")[1] or
        payload.get("algorithm")!="RSA-OAEP-SHA256+AES-256-GCM"):
        raise core.DualOffsiteDenied("PAIR_WRONG_KIND_OR_KEY")
    size=payload.get("source_bytes")
    part_size=payload.get("part_size")
    core._source_size(size,part_size)
    parts=(size+part_size-1)//part_size
    if type(payload.get("part_count")) is not int or payload["part_count"]!=parts:
        raise core.DualOffsiteDenied("PAIR_PART_COUNT_MISMATCH")
    for item in ("cipher_hash_chain_sha256","last_part_sha256","plaintext_sha256"):
        if type(payload.get(item)) is not str or not core.HEX64.fullmatch(payload[item]):
            raise core.DualOffsiteDenied("PAIR_INVALID_HASH_FIELD")
    bound=payload.get("aad_source_bytes",size)
    if type(bound) is not int or bound not in (0,size):
        raise core.DualOffsiteDenied("PAIR_AAD_SOURCE_BINDING_INVALID")
    if bound==0 and (payload.get("source_footer_sha256")!=core.digest(core.CPANEL_SOURCE_END_MARKER)
                     or payload.get("producer_exit_zero_observed") is not True):
        raise core.DualOffsiteDenied("PAIR_PRODUCER_EOF_NOT_PROVEN")
    chain=hashlib.sha256()
    last="0"*64
    for index in range(parts):
        path=base+kind+"/"+f"{index:08d}.gcm"
        length=min(part_size,size-index*part_size)+28
        bytes_by_cloud=[s.read_exact(path,length+1) for s in sinks]
        if any(type(v) is not bytes or len(v)!=length for v in bytes_by_cloud):
            raise core.DualOffsiteDenied("PAIR_CIPHER_PART_MISSING")
        if bytes_by_cloud[0]!=bytes_by_cloud[1]:
            raise core.DualOffsiteDenied("PAIR_CIPHER_PART_CLOUD_DIVERGENCE")
        last=core.digest(bytes_by_cloud[0])
        chain.update(bytes.fromhex(last))
    if chain.hexdigest()!=payload["cipher_hash_chain_sha256"] or last!=payload["last_part_sha256"]:
        raise core.DualOffsiteDenied("PAIR_CIPHER_CHAIN_NOT_VALID")
    return {"manifest_sha256":core.digest(values[0]),"source_bytes":size,
            "part_count":parts}


def finalize_technical_pair(sinks,*,set_id:str,expected_recipient_pubkey_sha256:str,
                            expected_main_source_commit:str) -> dict:
    base=core._source_name(set_id,"mysql").split("mysql/")[0]
    if type(sinks) is not tuple or len(sinks)!=2 or sinks[0] is sinks[1]:
        raise core.DualOffsiteDenied("PAIR_REQUIRES_TWO_INDEPENDENT_CLOUDS")
    if type(expected_recipient_pubkey_sha256) is not str or not core.HEX64.fullmatch(expected_recipient_pubkey_sha256):
        raise core.DualOffsiteDenied("PAIR_PUBLIC_KEY_FINGERPRINT_UNVERIFIED")
    if type(expected_main_source_commit) is not str or not SHA40.fullmatch(expected_main_source_commit):
        raise core.DualOffsiteDenied("PAIR_SOURCE_COMMIT_NOT_PINNED")
    mysql=_load_manifest(sinks,base,"mysql",expected_recipient_pubkey_sha256)
    files=_load_manifest(sinks,base,"files",expected_recipient_pubkey_sha256)
    receipt={
        "schema":PAIR_SCHEMA,"set_id":set_id,
        "expected_main_source_sha":expected_main_source_commit,
        "recipient_public_key_sha256":expected_recipient_pubkey_sha256,
        "technical_mysql":mysql,"technical_scoped_files":files,
        "kind_count":2,"two_cloud_part_and_manifest_readback":True,
        "consistency_between_live_sql_and_media_proven":False,
        "effective_production_passenger_mapping_proven":False,
        "independent_full_db_import_and_media_restore_proven":False,
        "owner_recovery_key_offsite_escrow_proven":False,
        "production_release_authorized":False,
        "payment_or_sale_authorized":False,
    }
    data=core.encoded(receipt)
    if len(data)>core.MAX_MANIFEST:
        raise core.DualOffsiteDenied("PAIR_RECEIPT_TOO_LONG")
    core._put_and_read_both(sinks,base+"complete-set-technical.json",data)
    return {
        "classification":"TWO_CLOUD_TWO_KIND_TECHNICAL_RECEIPT_NOT_FULL_RESTORE",
        "set_id":set_id,"files_present_kinds":2,
        "two_stores_part_bytes_rechecked":True,
        "technical_receipt_written_to_two_stores":True,
        "source_db_and_media_co_snapshot_proven":False,
        "isolated_real_sql_and_media_restore_proven":False,
        "owner_recovery_escrow_proven":False,
        "production_paid_challenge_available":False,
        "real_revenue_received":False,
        "production_or_customer_write_performed":False,
    }
