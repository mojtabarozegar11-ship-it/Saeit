#!/usr/bin/env python3
"""Append-only historical contract-year correction; never forge execution dates."""
import argparse,hashlib,json,os
from pathlib import Path
SCHEMA="saeit.factory.master-contract-year-correction.v1"
BEFORE="c72a282c253d6ab0f1d0feaff7690bcd4ead669bbabcc831065b0b6fc6855563"
AFTER="8c955cd28d99aa7f82db92403b9763dd9c7e33812b7e24c66a0a43c31b09b608"
def original():
    return {"schema":SCHEMA,
            "owner_corrected_contract_origin_year_jalali":1398,
            "contract_original_signed":"owner_attested_not_independently_examined",
            "typed_current_wording_preparation_year_jalali":1405,
            "date_correction":"1405 was mistakenly treated as the master contract year; the owner confirms 1398. 1405 is solely the typing/revision year.",
            "original_document_previous_sha256":BEFORE,
            "corrected_original_library_document_sha256":AFTER,
            "source_reference":"owner correction in ChatGPT dated 2026-10-21",
            "historical_original_signature_independently_verified":False,
            "current_additions_signed_in_1398_verified":False,
            "changes_other_contract_terms":False,
            "company_official_signing_authority_verified":False,
            "commercial_approval":False}
def serialized():return (json.dumps(original(),sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n").encode()
def install(workspace):
    base=Path(workspace)
    if not base.is_dir() or base.is_symlink():
        raise ValueError("PRIVATE_LEGAL_WORKSPACE_MISSING")
    folder=base/"legal-capacity"
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("ORIGINAL_LEGAL_LEDGER_NOT_INSTALLED")
    before=list(folder.glob("capacity-*.json"))
    if not before:raise ValueError("NO_ORIGINAL_LEDGER_TO_AMEND")
    if any(x.is_symlink() or not x.is_file() for x in before):
        raise ValueError("ORIGINAL_LEDGER_UNSAFE")
    previous_text=[x.read_text(encoding="utf8") for x in before]
    if not any(BEFORE in z for z in previous_text):
        raise ValueError("ORIGINAL_CONTRACT_EVIDENCE_NOT_PRESENT")
    contents=serialized();digest=hashlib.sha256(contents).hexdigest()
    correction=folder/("master-year-1398-"+digest[:24]+".json")
    if correction.is_symlink():raise ValueError("UNSAFE_LEDGER_CORRECTION")
    if correction.exists():
        if correction.read_bytes()!=contents:raise ValueError("CONFLICTING_YEAR_CORRECTION")
    else:
        with correction.open("xb") as f:
            f.write(contents);f.flush();os.fsync(f.fileno())
        os.chmod(correction,0o600)
    return {"status":"OWNER_ATTESTED_1398_YEAR_CORRECTION_INSTALLED",
            "master_contract_year":1398,"typed_revision_year":1405,
            "correction_sha256":digest,
            "preexisting_ledger_kept":True,
            "official_signature_authentication":False,
            "commercial_clearance":False}
def status(workspace):
    base=Path(workspace)/"legal-capacity"
    expect=serialized()
    items=list(base.glob("master-year-1398-*.json")) if base.is_dir() else []
    valid=[p for p in items if p.is_file() and not p.is_symlink() and p.read_bytes()==expect]
    return {"master_contract_correct_year":1398 if len(valid)==1 else None,
            "typed_revision_year":1405 if len(valid)==1 else None,
            "owner_asserted_signed_original_unverified":len(valid)==1,
            "contract_year_correction_ledger_verified":len(valid)==1,
            "commercial_release_enabled":False}
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["install","status"])
    parser.add_argument("--workspace",required=True)
    args=parser.parse_args()
    print(json.dumps(install(args.workspace) if args.command=="install" else status(args.workspace),sort_keys=True,ensure_ascii=False))
