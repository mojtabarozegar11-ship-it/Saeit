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
def terms_attestation():
    """User confirmation, NOT inspection/authentication of signed original."""
    return {
        "schema":"saeit.factory.master-contract-terms-owner-attestation.v1",
        "original_contract_execution_year_owner_attested_jalali":1398,
        "current_wording_same_as_signed_1398_original_owner_attested":True,
        "later_contract_clauses_added_owner_attested":False,
        "typed_copy_preparation_year_jalali":1405,
        "owner_confirmation_date":"2026-10-21",
        "corrected_library_document_sha256":AFTER,
        "independent_comparison_with_original_signed_copy_completed":False,
        "original_physical_signatures_independently_authenticated":False,
        "signing_legal_capacity_currently_independently_verified":False,
        "creates_new_contract_or_signatures":False,
        "commercial_release_approved":False,
    }
def attest_terms(workspace):
    base=Path(workspace)/"legal-capacity"
    if base.is_symlink() or not base.is_dir():
        raise ValueError("PRIVATE_LEGAL_LEDGER_NOT_PRESENT")
    expected=serialized()
    old=[p for p in base.glob("master-year-1398-*.json")
         if p.is_file() and not p.is_symlink() and p.read_bytes()==expected]
    if len(old)!=1:
        raise ValueError("CORRECTED_1398_CONTRACT_YEAR_RECORD_REQUIRED")
    blob=(json.dumps(terms_attestation(),sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n").encode()
    sha=hashlib.sha256(blob).hexdigest()
    dest=base/("master-terms-1398-"+sha[:24]+".json")
    if dest.is_symlink():raise ValueError("UNSAFE_OWNER_ATTESTATION")
    if dest.exists():
        if dest.read_bytes()!=blob:raise ValueError("IMMUTABLE_ATTESTATION_CONFLICT")
    else:
        with dest.open("xb") as output:
            output.write(blob);output.flush();os.fsync(output.fileno())
        os.chmod(dest,0o600)
    return {
        "master_contract_year":1398,
        "current_terms_same_as_original_1398_owner_attested":True,
        "new_clauses_after_1398_owner_attested":False,
        "attestation_sha256":sha,
        "independent_signed_original_comparison":False,
        "independent_signature_verification":False,
        "sale_or_quality_clearance":False,
    }

def dual_capacity_attestation():
    """Record direct user statement, not proof of original signatures or authority."""
    return {
        "schema":"saeit.factory.master-contract-dual-capacity-owner-attestation.v1",
        "contract_year_jalali":1398,
        "source":"owner_direct_conversation_confirmation_2026-10-21",
        "owner_attested_original_contract_signed":True,
        "signing_capacities_owner_attested":{
            "individual_personal_ip_owner":True,
            "company_managing_director_and_representative":True
        },
        "individual_professional_name":"مجتبی روزگار",
        "company_name":"شرکت کشت و صنعت زمرد ملل",
        "same_human_signed_in_two_distinct_capacities_owner_attested":True,
        "current_text_same_as_original_1398_owner_attested":True,
        "independently_inspected_original_signature":False,
        "company_signing_power_officially_verified_for_1398":False,
        "actual_contract_enforceability_independently_determined":False,
        "one_human_is_not_two_independent_qa_reviewers":True,
        "signed_qa_1000_certification_created":False,
        "commercial_release_authorized":False,
        "corrected_library_document_sha256":AFTER,
        "does_not_change_earlier_immutable_ledgers":True
    }
def attest_dual_capacity(workspace):
    """Separate immutable receipt tied to the already verified 1398 ledger."""
    base=Path(workspace)/"legal-capacity"
    if not base.is_dir() or base.is_symlink():
        raise ValueError("PRIVATE_LEGAL_LEDGER_NOT_PRESENT")
    expected_year=serialized()
    year_receipts=[p for p in base.glob("master-year-1398-*.json")
                   if p.is_file() and not p.is_symlink() and p.read_bytes()==expected_year]
    terms_expected=(json.dumps(terms_attestation(),sort_keys=True,
                    ensure_ascii=False,separators=(",",":"))+"\n").encode()
    terms_receipts=[p for p in base.glob("master-terms-1398-*.json")
                    if p.is_file() and not p.is_symlink() and p.read_bytes()==terms_expected]
    if len(year_receipts)!=1 or len(terms_receipts)!=1:
        raise ValueError("SIGNED_1398_YEAR_AND_TERMS_OWNER_ATTESTATIONS_REQUIRED")
    payload=(json.dumps(dual_capacity_attestation(),sort_keys=True,
             ensure_ascii=False,separators=(",",":"))+"\n").encode()
    digest=hashlib.sha256(payload).hexdigest()
    target=base/("master-two-capacities-1398-"+digest[:24]+".json")
    if target.is_symlink():raise ValueError("UNSAFE_DUAL_CAPACITY_LEDGER")
    if target.exists():
        if target.read_bytes()!=payload:raise ValueError("CONFLICTING_DUAL_CAPACITY_LEDGER")
    else:
        with target.open("xb") as output:
            output.write(payload);output.flush();os.fsync(output.fileno())
        os.chmod(target,0o600)
    return {
        "owner_attested_personal_signature":True,
        "owner_attested_company_representative_signature":True,
        "same_human_two_distinct_legal_roles":True,
        "independent_original_signature_verification":False,
        "official_company_authority_verified":False,
        "qa_or_commercial_approval":False,
        "receipt_sha256":digest,
        "prior_immutable_ledgers_preserved":True
    }

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["install","status","attest-terms","attest-dual-capacity"])
    parser.add_argument("--workspace",required=True)
    args=parser.parse_args()
    print(json.dumps(install(args.workspace) if args.command=="install" else attest_terms(args.workspace) if args.command=="attest-terms" else attest_dual_capacity(args.workspace) if args.command=="attest-dual-capacity" else status(args.workspace),sort_keys=True,ensure_ascii=False))
