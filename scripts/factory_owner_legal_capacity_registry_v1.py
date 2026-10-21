#!/usr/bin/env python3
"""Private individual-vs-company legal-capacity dossier for quality approvals.

Source: owner-supplied foundational/company text and UNSIGNED 1405 master
contract. File SHA256 hashes bind exact uploaded documents, not official
registry authenticity or legal signature validity. Never conflates the human
owner with the limited liability company and never grants expert approval.
No private identity numbers, scans, signatures, or addresses are uploaded.
"""
import argparse,hashlib,importlib.util,json,os,re,sys
from pathlib import Path

SCHEMA="saeit.factory.legal-capacity-context.v1"
CONSOLE_ID="owner_mojtaba_roozegar"
DOCS={
  "company_memo_user_supplied_1398_claim":{
    "sha256":"73862797de3e1e46d8901045d8055cb55c6a2411edeb6f9a6650d3ea6522ed24",
    "file_label":"شرکت نامه شرکت کشت و صنعت زمرد.docx",
    "type":"owner_uploaded_private_foundation_company_text",
    "original_historical_execution_owner_attested":True,
    "original_signature_independently_inspected":False},
  "company_activity_articles_user_supplied":{
    "sha256":"8242529cc8c116628385db04b2dc678b83cf9d654559f3a6ecfc0831a21d4a76",
    "file_label":"اساسنامه شرکت کشت و صنعت زمرد ملل.docx",
    "type":"owner_uploaded_articles_activity_description",
    "original_signature_independently_inspected":False},
  "master_rights_1405_unsigned_draft":{
    "sha256":"c72a282c253d6ab0f1d0feaff7690bcd4ead669bbabcc831065b0b6fc6855563",
    "file_label":"قرارداد_مادر_مالکیت_شخصی_و_بهره_برداری_زمرد_ملل_پیشنویس.docx",
    "type":"unsigned_revised_master_contract_draft_1405",
    "signed_or_executed":False},
}
HEX=re.compile(r"^[a-f0-9]{64}$")
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def dossier():
    return {
       "schema":SCHEMA,
       "visibility":"private_internal_only",
       "natural_person":{
           "legal_name_fa":"مجتبی گلستانی‌نیک",
           "professional_name_fa":"مجتبی روزگار",
           "name_relationship":"owner_attested_former_family_name_and_professional_identity",
           "personal_national_id_in_public_or_repo":False,
           "identity_evidence_status":"owner_declaration_and_uploaded_documents_not_independently_authenticated",
           "declared_economic_rights_holder_for_eligible_products":True,
           "rights_depend_on_real_per_asset_title_evidence":True,
       },
       "legal_person":{
           "legal_name_fa":"شرکت کشت و صنعت زمرد ملل",
           "legal_form":"limited_liability_company",
           "registry_number_owner_declared":"3110",
           "national_company_id_owner_documents":"14008746024",
           "national_id_not_crosschecked_with_registry":True,
           "founding_date_jalali_owner_declared":"1398/08/16",
           "registered_city_owner_declared":"مرودشت",
           "legal_personality_separate_from_natural_person":True,
           "sole_owner_of_all_company_shares":False,
           "shareholding_claim_in_user_company_text":{
               "owner_99_percent":"مجتبی روزگار",
               "other_party_1_percent":"سمن روزگار",
               "verified_official_share_ledger":False,
           },
           "managing_director_owner_declared":"مجتبی روزگار",
           "individual_signatory_claimed_by_company_text":True,
           "official_current_directorship_verified":False,
           "current_signatory_authority_officially_verified":False,
           "operational_commercial_service_provider_only":True,
           "auto_transferred_product_ip":False,
       },
       "legal_relationship":{
           "owner_is_one_human_who_may_act_in_personal_and_company_representative_capacities":True,
           "capacities_legally_distinct":True,
           "personally_owned_IP_is_not_company_IP":True,
           "master_contract_rewrite_signed_and_executed":False,
           "company_operational_permission_contract_executed_verified":False,
           "independent_related_party_transaction_authorization_verified":False,
           "owner_company_representation_is_not_independent_technical_review":True,
       },
       "reviewer_registration":{
           "owner_reviewer_id":CONSOLE_ID,
           "one_real_person_not_two_independent_reviewers":True,
           "owner_role":"owner",
           "natural_person_owner_signature_available":False,
           "corporate_representative_authority_verified":False,
           "independent_specialist_reviewers_still_required":True,
           "expert_keys_or_signatures_generated":False,
           "trusted_root_owner_key_registered":False,
       },
       "source_files":DOCS,
       "source_document_count":len(DOCS),
       "source_evidence_note":"Only hashes and file titles recorded; source bytes remain in user Library and are not uploaded to VPS by this operation.",
       "conflict_and_gap_checks":{
           "historical_1398_foundation_not_equivalent_to_signed_1405_master":True,
           "formal_name_professional_name_link_requires_documentary_confirmation":True,
           "company_id_current_registry_confirmation_required":True,
           "sole_signature_claim_in_company_text_requires_official_current_confirmation":True,
           "independent_human_QA_identity_check_required":True,
       },
       "current_legal_capacity_status":"OWNER_CLAIMS_RECORDED_EXTERNAL_REGISTRY_AND_AUTHORITY_PENDING",
       "real_signatures_verified":False,
       "commercial_clearance_allowed":False,
       "quality_1000_approval_granted":False,
    }
def validate(doc):
    if not isinstance(doc,dict) or doc!=dossier():
        raise ValueError("LEGAL_CAPACITY_CONTEXT_TAMPER_OR_UNAUTHORIZED_AUTOVERIFICATION")
    if doc["natural_person"]["legal_name_fa"]==doc["legal_person"]["legal_name_fa"]:
        raise ValueError("NATURAL_LEGAL_PERSON_MERGED")
    if doc["reviewer_registration"]["natural_person_owner_signature_available"]:
        raise ValueError("NO_SELF_GENERATED_SIGNATURE")
    if doc["legal_relationship"]["master_contract_rewrite_signed_and_executed"]:
        raise ValueError("DRAFT_MUST_NOT_BE_BACKDATED_OR_SELF_SIGNED")
    for value in doc["source_files"].values():
        if not HEX.fullmatch(value["sha256"]):raise ValueError("DOCUMENT_HASH_INVALID")
    return True
def install(workspace,make_owner_invitation=True):
    base=Path(workspace)
    if base.is_symlink():raise ValueError("PRIVATE_WORKSPACE_SYMLINK")
    base.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(base,0o700)
    doc=dossier();validate(doc)
    serialized=canonical(doc)+b"\n"
    ledger=base/"legal-capacity"
    if ledger.is_symlink():raise ValueError("LEGAL_LEDGER_SYMLINK")
    ledger.mkdir(mode=0o700,exist_ok=True)
    os.chmod(ledger,0o700)
    artifact=ledger/("capacity-"+sha(serialized)[:24]+".json")
    if artifact.is_symlink():raise ValueError("LEDGER_SYMLINK")
    if artifact.exists():
        if artifact.read_bytes()!=serialized:raise ValueError("IMMUTABLE_LEGAL_LEDGER_CONFLICT")
    else:
        with artifact.open("xb") as stream:
            stream.write(serialized);stream.flush();os.fsync(stream.fileno())
        os.chmod(artifact,0o600)
    invitation_status="not_requested"
    if make_owner_invitation:
        module_path=base/"factory_quality_reviewer_console_v1.py"
        if not module_path.is_file() or module_path.is_symlink():
            raise ValueError("REVIEWER_CONSOLE_NOT_DEPLOYED")
        spec=importlib.util.spec_from_file_location("private_reviewer_console",module_path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        pending=base/"reviewer-requests"/(CONSOLE_ID+".invite.json")
        if pending.is_file() and not pending.is_symlink():
            existing=json.loads(pending.read_text())
            if existing.get("reviewer_id")!=CONSOLE_ID or existing.get("role")!="owner":
                raise ValueError("OWNER_INVITATION_WRONG_CAPACITY")
            invitation_status="owner_invitation_existing"
        else:
            module.invite(base,CONSOLE_ID,"owner")
            invitation_status="owner_invitation_created_without_signature"
    return {
        "schema":"saeit.factory.legal-capacity-install-receipt.v1",
        "dossier_sha256":sha(serialized),"evidence_source_files":len(DOCS),
        "natural_person_recorded":True,"separate_legal_person_recorded":True,
        "claimed_company_signatory_capacity_recorded":True,
        "official_registry_verification":False,
        "actual_owner_signature":False,
        "independent_specialist_certificates":0,
        "company_authority_verified":False,
        "commercial_approval":False,
        "owner_invitation_status":invitation_status
    }
def audit(workspace):
    root=Path(workspace)/"legal-capacity"
    if not root.is_dir() or root.is_symlink():raise ValueError("LEGAL_LEDGER_NOT_INSTALLED")
    candidates=list(root.glob("capacity-*.json"))
    expected=canonical(dossier())+b"\n"
    exact=[f for f in candidates if f.is_file() and not f.is_symlink() and f.read_bytes()==expected]
    if len(exact)!=1:raise ValueError("LEGAL_IDENTITY_DOSSIER_MISSING_OR_CONFLICT")
    return {"source_dossier_sha256":sha(expected),"legal_capacity_recorded":True,
            "natural_person_identity_authenticated":False,
            "company_legal_signing_authority_verified":False,
            "independent_expert_certification":False,
            "release_allowed":False}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("operation",choices=["install","status"])
    p.add_argument("--workspace",required=True)
    p.add_argument("--no-owner-invitation",action="store_true")
    a=p.parse_args()
    result=install(a.workspace,not a.no_owner_invitation) if a.operation=="install" else audit(a.workspace)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
