#!/usr/bin/env python3
"""Private specialist signing console. No fake expert or server-side private keys.

Workflow: invite -> reviewer proves possession -> owner verifies real identity
offline -> prepares registry -> owner signs registry on OFFLINE trusted device
-> install only with externally pinned root key -> reviewer signs exact decision
on own device -> verify multi-role clearance. Default: no reviewer authorized.

The factory, GitHub, VPS and this script NEVER create expert identities.
"""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib,importlib.util,json,os
from pathlib import Path
import re,secrets,subprocess,tempfile

SCHEMA="saeit.factory.reviewer-invite.v1"
RESPONSE="saeit.factory.reviewer-key-response.v1"
KEY_SCHEMA="saeit.factory.trusted-reviewer-keys.v1"
ROLES=("domain_specialist","independent_quality_auditor","rights_reviewer","owner")
DELEGATE_ROLE="owner_delegate_agent"
ENROLLMENT_ROLES=ROLES+(DELEGATE_ROLE,)
DELEGATION_SCHEMA="saeit.factory.owner-agent-delegation.v1"
DELEGATION_SCOPE="quality-owner-operational-signoff-only"
HEX=re.compile(r"^[0-9a-f]{64}$")
def canon(d):return json.dumps(d,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def private_dir(p):
    p=Path(p);p.mkdir(parents=True,exist_ok=True,mode=0o700)
    if p.is_symlink():raise ValueError("SYMLINK_FORBIDDEN")
    os.chmod(p,0o700);return p
def save_new(path,data):
    path=Path(path)
    if path.is_symlink():raise ValueError("SYMLINK_FORBIDDEN")
    with path.open("xb") as f:
        f.write(canon(data)+b"\n");f.flush();os.fsync(f.fileno())
    os.chmod(path,0o600)
    return path
def openssl_sign(private,payload):
    with tempfile.TemporaryDirectory(prefix="factory-signer-") as d:
        root=Path(d);(root/"message").write_bytes(payload)
        command=["openssl","pkeyutl","-sign","-rawin",
                 "-inkey",str(private),"-in",str(root/"message"),
                 "-out",str(root/"signature")]
        subprocess.run(command,check=True,timeout=15,capture_output=True)
        result=(root/"signature").read_bytes()
        if len(result)!=64:raise ValueError("NOT_ED25519_SIGNATURE")
        return result.hex()
def openssl_verify(pub,payload,sig):
    if not isinstance(sig,str) or not re.fullmatch(r"[0-9a-f]{128}",sig):return False
    try:
        with tempfile.TemporaryDirectory(prefix="factory-verification-") as d:
            root=Path(d);(root/"key.pem").write_text(pub)
            (root/"message").write_bytes(payload)
            (root/"sig").write_bytes(bytes.fromhex(sig))
            done=subprocess.run(["openssl","pkeyutl","-verify","-pubin","-rawin",
                   "-inkey",str(root/"key.pem"),"-in",str(root/"message"),
                   "-sigfile",str(root/"sig")],timeout=15,capture_output=True)
            return done.returncode==0
    except (OSError,subprocess.TimeoutExpired):return False
def make_delegation(root_private,root_public,agent_public,reviewer_id,families,days,output):
    """MUST run on an offline owner-controlled signing device, never factory VPS."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]{4,64}",reviewer_id):
        raise ValueError("AGENT_REVIEWER_ID_INVALID")
    items=[s.strip() for s in families.split(",")]
    if (not isinstance(days,int) or not 1<=days<=90
            or not 1<=len(items)<=49 or len(set(items))!=len(items)
            or any(not re.fullmatch(r"F(?:0[1-9]|[1-3][0-9]|4[0-9])",f) for f in items)):
        raise ValueError("AGENT_SCOPE_OR_EXPIRY_INVALID")
    owner_pub=Path(root_public).read_text()
    agent_pub=Path(agent_public).read_text()
    now=datetime.now(timezone.utc)
    grant={"schema":DELEGATION_SCHEMA,"reviewer_id":reviewer_id,
           "agent_public_key_sha256":sha(agent_pub.encode()),
           "owner_root_public_key_sha256":sha(owner_pub.encode()),
           "scope":DELEGATION_SCOPE,"authorized_family_ids":sorted(items),
           "not_before_utc":(now-timedelta(minutes=1)).isoformat(),
           "expires_at_utc":(now+timedelta(days=days)-timedelta(minutes=1)).isoformat()}
    sig=openssl_sign(root_private,canon(grant))
    if not openssl_verify(owner_pub,canon(grant),sig):
        raise ValueError("OWNER_ROOT_KEY_MISMATCH")
    return save_new(output,{"delegation":grant,"signature_hex":sig,
                            "owner_root_public_key_pem":owner_pub})

def invite(workspace,reviewer_id,role):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{4,64}",reviewer_id) or role not in ENROLLMENT_ROLES:
        raise ValueError("REVIEWER_ID_OR_ROLE_INVALID")
    d=private_dir(Path(workspace)/"reviewer-requests")
    path=d/(reviewer_id+".invite.json")
    now=datetime.now(timezone.utc)
    data={"schema":SCHEMA,"reviewer_id":reviewer_id,"role":role,
          "nonce":secrets.token_hex(32),"issued_at_utc":now.isoformat(),
          "expires_at_utc":(now+timedelta(days=14)).isoformat(),
          "identity_verified":False,"signature_submitted":False,
          "owner_approval":False}
    return save_new(path,data)
def answer(invitation,private_key,public_key,output):
    i=json.loads(Path(invitation).read_text())
    if i.get("schema")!=SCHEMA or i.get("role") not in ENROLLMENT_ROLES:
        raise ValueError("INVALID_INVITE")
    if datetime.now(timezone.utc)>datetime.fromisoformat(i["expires_at_utc"]):
        raise ValueError("EXPIRED_INVITE")
    key=Path(public_key).read_text()
    payload={"invite_sha256":sha(canon(i)),
             "reviewer_id":i["reviewer_id"],"role":i["role"],
             "public_key_sha256":sha(key.encode())}
    signature=openssl_sign(private_key,canon(payload))
    if not openssl_verify(key,canon(payload),signature):
        raise ValueError("PRIVATE_PUBLIC_KEY_MISMATCH")
    response={"schema":RESPONSE,"reviewer_id":i["reviewer_id"],
              "role":i["role"],"public_key_pem":key,
              "challenge_payload":payload,"challenge_signature_hex":signature}
    return save_new(output,response)
def verify_response(invite_doc,response_doc):
    i,r=invite_doc,response_doc
    if i.get("schema")!=SCHEMA or r.get("schema")!=RESPONSE or i.get("reviewer_id")!=r.get("reviewer_id") or i.get("role")!=r.get("role"):
        raise ValueError("INVALID_REVIEWER_CHALLENGE_IDENTITY")
    if datetime.now(timezone.utc)>datetime.fromisoformat(i["expires_at_utc"]):
        raise ValueError("EXPIRED_INVITE")
    expected={"invite_sha256":sha(canon(i)),
              "reviewer_id":i["reviewer_id"],"role":i["role"],
              "public_key_sha256":sha(r["public_key_pem"].encode())}
    if expected!=r.get("challenge_payload") or not openssl_verify(r["public_key_pem"],canon(expected),r.get("challenge_signature_hex")):
        raise ValueError("REVIEWER_PUBLIC_KEY_POSSESSION_UNVERIFIED")
    return True
def prepare_registry(workspace,verified_entries):
    """Each entry: invitation, signed response and an identity-review evidence file.

    Collecting bytes is NOT a completed identity verification. Authority must
    investigate and sign the registry OFFLINE before installation will work.
    """
    users={}
    for entry in verified_entries:
        i=json.loads(Path(entry["invitation"]).read_text())
        response=json.loads(Path(entry["response"]).read_text())
        verify_response(i,response)
        evidence=Path(entry["identity_verification_record"])
        if evidence.is_symlink() or not evidence.is_file() or not 32<=evidence.stat().st_size<=2_000_000:
            raise ValueError("IDENTITY_REVIEW_RECORD_MISSING")
        reviewer=i["reviewer_id"]
        if reviewer in users:raise ValueError("DUPLICATE_REVIEWER")
        item={"role":i["role"],"public_key_pem":response["public_key_pem"],
              "identity_verification_evidence_sha256":sha(evidence.read_bytes()),
              "externally_identity_verified":i["role"]!=DELEGATE_ROLE,"active":True}
        if i["role"]==DELEGATE_ROLE:
            if "owner_delegation_record" not in entry:
                raise ValueError("SIGNED_OWNER_AGENT_DELEGATION_REQUIRED")
            grant_file=Path(entry["owner_delegation_record"])
            if grant_file.is_symlink() or not grant_file.is_file():
                raise ValueError("OWNER_AGENT_DELEGATION_FILE_MISSING")
            certificate=json.loads(grant_file.read_text())
            grant=certificate.get("delegation")
            root_pub=certificate.get("owner_root_public_key_pem")
            if (not isinstance(grant,dict) or not isinstance(root_pub,str)
                    or grant.get("reviewer_id")!=reviewer
                    or grant.get("agent_public_key_sha256")!=sha(response["public_key_pem"].encode())
                    or grant.get("owner_root_public_key_sha256")!=sha(root_pub.encode())
                    or not openssl_verify(root_pub,canon(grant),certificate.get("signature_hex"))):
                raise ValueError("OWNER_AGENT_DELEGATION_UNVERIFIED")
            item.update({"reviewer_id":reviewer,"agent_identity_verified":True,
                         "owner_delegation":grant,
                         "owner_delegation_signature_hex":certificate["signature_hex"]})
        users[reviewer]=item
    proposal={"schema":KEY_SCHEMA,"reviewers":users}
    return save_new(private_dir(Path(workspace)/"registry-proposals")/
                    ("proposal-"+sha(canon(proposal))[:24]+".json"),proposal)
def sign_registry(proposal,root_private,root_public,output):
    """Root signer MUST stay on external owner-controlled trusted machine."""
    d=json.loads(Path(proposal).read_text())
    if d.get("schema")!=KEY_SCHEMA or not isinstance(d.get("reviewers"),dict):
        raise ValueError("REGISTRY_PROPOSAL_INVALID")
    pub=Path(root_public).read_text()
    for name,entry in d["reviewers"].items():
        if entry.get("role")==DELEGATE_ROLE:
            grant=entry.get("owner_delegation",{})
            if (grant.get("reviewer_id")!=name
                    or grant.get("owner_root_public_key_sha256")!=sha(pub.encode())
                    or not openssl_verify(pub,canon(grant),entry.get("owner_delegation_signature_hex"))):
                raise ValueError("OWNER_AGENT_DELEGATION_NOT_FROM_THIS_ROOT")
    payload=canon({"schema":KEY_SCHEMA,"reviewers":d["reviewers"]})
    sig=openssl_sign(root_private,payload)
    if not openssl_verify(pub,payload,sig):raise ValueError("OWNER_ROOT_KEY_MISMATCH")
    signed=dict(d,trusted_root_public_key_pem=pub,root_signature_hex=sig)
    return save_new(output,signed)
def install_registry(workspace,signed_file,operator_root_fingerprint):
    d=json.loads(Path(signed_file).read_text())
    if not re.fullmatch(r"[a-f0-9]{64}",operator_root_fingerprint):
        raise ValueError("NO_PINNED_OWNER_TRUST_ROOT")
    public=d.get("trusted_root_public_key_pem","")
    if sha(public.encode())!=operator_root_fingerprint or not openssl_verify(
        public,canon({"schema":KEY_SCHEMA,"reviewers":d.get("reviewers")}),
        d.get("root_signature_hex")):
        raise ValueError("OWNER_ROOT_SIGNATURE_INVALID")
    for name,entry in d["reviewers"].items():
        if entry.get("role")==DELEGATE_ROLE:
            grant=entry.get("owner_delegation",{})
            if (grant.get("reviewer_id")!=name
                    or grant.get("owner_root_public_key_sha256")!=operator_root_fingerprint
                    or not openssl_verify(public,canon(grant),entry.get("owner_delegation_signature_hex"))):
                raise ValueError("INVALID_OWNER_AGENT_DELEGATION")
    out=private_dir(Path(workspace)/"quality-trust")/"trusted-reviewers.json"
    if out.exists():
        if out.read_bytes()!=canon(d)+b"\n":
            raise ValueError("PREVIOUS_TRUST_REGISTRY_REQUIRES_MANUAL_ROTATION")
        return out
    return save_new(out,d)
def sign_decision(decision_path,private_key,reviewer_id,role,output,acknowledge,operational_policy_checked=False):
    if (role not in ENROLLMENT_ROLES or not re.fullmatch(r"[A-Za-z0-9_.-]{4,64}",reviewer_id)
            or (not operational_policy_checked if role==DELEGATE_ROLE else not acknowledge)):
        raise ValueError("PERSONAL_REVIEW_AND_EXPLICIT_ACKNOWLEDGMENT_REQUIRED")
    d=json.loads(Path(decision_path).read_text())
    ids={"Q%03d"%x for x in range(1,101)}
    if (not isinstance(d.get("100_groups"),dict) or set(d["100_groups"])!=ids
        or any(type(v) is not int or v!=10 for v in d["100_groups"].values())
        or d.get("unresolved_critical_defects")!=0):
        raise ValueError("100_INDEPENDENT_CRITERIA_NOT_APPROVED")
    signature=openssl_sign(private_key,canon(d))
    return save_new(output,{"reviewer_id":reviewer_id,"role":role,"signature_hex":signature,
                            "decision_sha256":sha(canon(d))})
def summary(workspace):
    root=Path(workspace)
    pending=len(list((root/"reviewer-requests").glob("*.invite.json"))) if (root/"reviewer-requests").is_dir() else 0
    trust=root/"quality-trust"/"trusted-reviewers.json"
    enrolled=0;roles=[]
    if trust.is_file() and not trust.is_symlink():
        doc=json.loads(trust.read_text());enrolled=len(doc.get("reviewers",{}))
        roles=sorted(x.get("role") for x in doc.get("reviewers",{}).values())
    return {"schema":"saeit.factory.reviewer-console-status.v1",
            "pending_invitations":pending,"trusted_reviewer_count":enrolled,
            "trusted_roles":roles,
            "all_four_roles_registered":set(roles)==set(ROLES),
            "actual_specialist_approvals_created_by_console":0,
            "commercial_release_allowed_by_console":False}
def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="command",required=True)
    for name in ("status","invite","respond","prepare-registry","sign-registry","install-registry","sign-decision","sign-agent-delegation"):
        q=sub.add_parser(name)
        if name in ("status","invite","prepare-registry","install-registry"):q.add_argument("--workspace",required=True)
        if name=="invite":
            q.add_argument("--reviewer-id",required=True);q.add_argument("--role",required=True,choices=ENROLLMENT_ROLES)
        if name=="respond":
            for key in ("invitation","private-key","public-key","output"):q.add_argument("--"+key,required=True)
        if name=="prepare-registry":q.add_argument("--entries",required=True,help="JSON array of invite/response/identity evidence file paths")
        if name=="sign-registry":
            for key in ("proposal","root-private","root-public","output"):q.add_argument("--"+key,required=True)
        if name=="install-registry":
            q.add_argument("--signed-registry",required=True);q.add_argument("--root-sha256",required=True)
        if name=="sign-decision":
            for key in ("decision","private-key","reviewer-id","role","output"):q.add_argument("--"+key,required=True)
            q.add_argument("--i-personally-reviewed-all-evidence",action="store_true")
            q.add_argument("--operational-policy-checked",action="store_true")
        if name=="sign-agent-delegation":
            for key in ("root-private","root-public","agent-public","reviewer-id","families","output"):
                q.add_argument("--"+key,required=True)
            q.add_argument("--days",type=int,default=30)
    a=p.parse_args()
    if a.command=="status":res=summary(a.workspace)
    elif a.command=="invite":res={"invitation_file":str(invite(a.workspace,a.reviewer_id,a.role))}
    elif a.command=="respond":res={"response_file":str(answer(a.invitation,a.private_key,a.public_key,a.output))}
    elif a.command=="prepare-registry":
        res={"unsigned_identity_registry_proposal":str(prepare_registry(a.workspace,json.loads(Path(a.entries).read_text())))}
    elif a.command=="sign-registry":
        res={"signed_registry":str(sign_registry(a.proposal,a.root_private,a.root_public,a.output))}
    elif a.command=="install-registry":
        res={"registry_installed":str(install_registry(a.workspace,a.signed_registry,a.root_sha256))}
    elif a.command=="sign-agent-delegation":
        res={"owner_signed_agent_delegation":str(make_delegation(a.root_private,a.root_public,
              a.agent_public,a.reviewer_id,a.families,a.days,a.output))}
    else:
        res={"signature_file":str(sign_decision(a.decision,a.private_key,a.reviewer_id,a.role,a.output,
              a.i_personally_reviewed_all_evidence,a.operational_policy_checked))}
    print(json.dumps(res,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
