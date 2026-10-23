"""Real OpenSSL private reviewer on-boarding -> verified registry -> signed 100x10.
All test identities are ephemeral; none are genuine human expert credentials.
"""
import hashlib,importlib.util,json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name):
    p=ROOT/"scripts"/(name+".py")
    s=importlib.util.spec_from_file_location(name,p)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
console=load("factory_quality_reviewer_console_v1")
checker=load("factory_quality_signed_approval_v1")

def make_pair(root,name):
    private=root/(name+".private.pem")
    public=root/(name+".public.pem")
    subprocess.run(["openssl","genpkey","-algorithm","Ed25519","-out",str(private)],
                   check=True,capture_output=True)
    with public.open("wb") as f:
        subprocess.run(["openssl","pkey","-in",str(private),"-pubout"],
                       check=True,stdout=f,stderr=subprocess.PIPE)
    return private,public

class RealReviewerService(unittest.TestCase):
    def test_private_onboarding_genuine_keys_authority_and_sign_all_100(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);work=base/"private-factory"
            self.assertEqual(console.summary(work)["trusted_reviewer_count"],0)
            requests=[];keys={}
            for role in console.ROLES:
                reviewer="actual_test_"+role
                private,public=make_pair(base,reviewer)
                keys[role]=(private,public)
                invitation=console.invite(work,reviewer,role)
                response=base/(reviewer+".response.json")
                console.answer(invitation,private,public,response)
                evidence=base/(reviewer+".identity-review.txt")
                evidence.write_text("Externally inspected identity evidence; test only, NOT a real identity verification.")
                requests.append({"invitation":str(invitation),"response":str(response),
                                 "identity_verification_record":str(evidence)})
            proposal=console.prepare_registry(work,requests)
            root_private,root_public=make_pair(base,"root_owner_offline")
            signed=base/"signed-registry.json"
            console.sign_registry(proposal,root_private,root_public,signed)
            fingerprint=hashlib.sha256(root_public.read_bytes()).hexdigest()
            installed=console.install_registry(work,signed,fingerprint)
            self.assertEqual(console.summary(work)["trusted_reviewer_count"],4)
            self.assertTrue(console.summary(work)["all_four_roles_registered"])
            doc=json.loads(installed.read_text())
            with patch.dict(os.environ,{"FACTORY_QA_TRUST_ROOT_SHA256":fingerprint}):
                self.assertEqual(len(checker.validate_key_registry(doc)),4)
            artifact=base/"release.bin";artifact.write_bytes(b"real measured bytes")
            catalog=base/"catalog.json";catalog.write_text("one hundred individual checks")
            gate={"schema":"saeit.factory.global-premium-quality.v1",
                  "family_id":"F28","technical_test_passed":True,
                  "blockers":[{"code":"P0_INDEPENDENT_ATTESTATION_NOT_AUTHENTICATED"},
                              {"code":"P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED"}]}
            decision={"family_id":"F28","artifact_sha256":checker.digest(artifact),
                      "quality_catalog_sha256":checker.digest(catalog),
                      "gate_report_sha256":hashlib.sha256(checker.canonical(gate)).hexdigest(),
                      "evidence_manifest_sha256":"f"*64,
                      "unresolved_critical_defects":0,
                      "100_groups":{"Q%03d"%i:10 for i in range(1,101)}}
            decision_path=base/"review-decision.json"
            decision_path.write_text(json.dumps(decision))
            signatures=[]
            for role,(private,_) in keys.items():
                out=base/(role+".signed.json")
                console.sign_decision(decision_path,private,"actual_test_"+role,role,out,True)
                sr=json.loads(out.read_text())
                signatures.append({key:sr[key] for key in ("reviewer_id","role","signature_hex")})
            with patch.dict(os.environ,{"FACTORY_QA_TRUST_ROOT_SHA256":fingerprint}):
                r=checker.inspect_approval({"schema":checker.SCHEMA,
                                           "decision":decision,"approvals":signatures},
                                          gate,artifact,catalog,doc)
            self.assertTrue(r["eligible"],r["blocking_reasons"])
            self.assertFalse(r["publication_executed"])
            self.assertFalse(r["payment_activated"])
    def test_offline_owner_agent_enrollment_requires_root_signed_scoped_grant(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);workspace=base/"private-factory"
            root_private,root_public=make_pair(base,"offline-root")
            other_private,other_public=make_pair(base,"attacker-root")
            agent_private,agent_public=make_pair(base,"master-agent")
            self.assertTrue(agent_private.exists())
            reviewer_id="agent_moj_1ro_1"
            invitation=console.invite(workspace,reviewer_id,console.DELEGATE_ROLE)
            response=base/"agent-key-response.json"
            console.answer(invitation,agent_private,agent_public,response)
            evidence=base/"agent-provenance.txt"
            evidence.write_text("Synthetic agent identity proof: TEST ONLY.")
            cert=base/"scoped-delegation.json"
            console.make_delegation(root_private,root_public,agent_public,reviewer_id,"F14,F28",30,cert)
            entry={"invitation":str(invitation),"response":str(response),
                   "identity_verification_record":str(evidence),
                   "owner_delegation_record":str(cert)}
            with self.assertRaisesRegex(ValueError,"SIGNED_OWNER_AGENT_DELEGATION_REQUIRED"):
                console.prepare_registry(workspace,[{k:v for k,v in entry.items()
                                                    if k!="owner_delegation_record"}])
            proposal=console.prepare_registry(workspace,[entry])
            with self.assertRaisesRegex(ValueError,"OWNER_AGENT_DELEGATION_NOT_FROM_THIS_ROOT"):
                console.sign_registry(proposal,other_private,other_public,base/"wrong-root.json")
            signed=base/"owner-signed.json"
            console.sign_registry(proposal,root_private,root_public,signed)
            fingerprint=hashlib.sha256(root_public.read_bytes()).hexdigest()
            installed=console.install_registry(workspace,signed,fingerprint)
            doc=json.loads(installed.read_text())
            self.assertFalse(doc["reviewers"][reviewer_id]["externally_identity_verified"])
            self.assertTrue(doc["reviewers"][reviewer_id]["agent_identity_verified"])
            with patch.dict(os.environ,{"FACTORY_QA_TRUST_ROOT_SHA256":fingerprint}):
                self.assertEqual(len(checker.validate_key_registry(doc)),1)
            self.assertFalse(console.summary(workspace)["all_four_roles_registered"])

    def test_agent_signoff_needs_separate_operational_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);priv,_=make_pair(base,"agent")
            decision={"100_groups":{"Q%03d"%i:10 for i in range(1,101)},
                      "unresolved_critical_defects":0}
            source=base/"decision.json";source.write_text(json.dumps(decision))
            out=base/"agent.sig.json"
            with self.assertRaisesRegex(ValueError,"PERSONAL_REVIEW"):
                console.sign_decision(source,priv,"owner_agent123",console.DELEGATE_ROLE,out,True)
            console.sign_decision(source,priv,"owner_agent123",console.DELEGATE_ROLE,out,
                                  False,operational_policy_checked=True)
            self.assertTrue(out.is_file())

    def test_root_signature_cannot_be_installed_with_wrong_pin(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);priv,pub=make_pair(base,"root")
            proposal=base/"empty_proposal.json"
            proposal.write_text(json.dumps({"schema":console.KEY_SCHEMA,"reviewers":{}}))
            target=base/"signed.json"
            console.sign_registry(proposal,priv,pub,target)
            with self.assertRaisesRegex(ValueError,"OWNER_ROOT_SIGNATURE_INVALID"):
                console.install_registry(base/"private",target,"f"*64)
    def test_no_one_can_claim_approval_without_personal_review(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);priv,_=make_pair(base,"reviewer")
            doc=base/"dec.json";doc.write_text(json.dumps({"100_groups":{"Q%03d"%i:10 for i in range(1,101)},
                "unresolved_critical_defects":0}))
            with self.assertRaisesRegex(ValueError,"PERSONAL_REVIEW"):
                console.sign_decision(doc,priv,"reviewer123","owner",base/"x.json",False)
    def test_fake_or_altered_key_possession_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);priv,pub=make_pair(base,"reviewer")
            invite=console.invite(base,"reviewer123","domain_specialist")
            response=base/"response.json"
            console.answer(invite,priv,pub,response)
            edited=json.loads(response.read_text())
            edited["challenge_payload"]["role"]="owner"
            with self.assertRaisesRegex(ValueError,"REVIEWER_PUBLIC_KEY_POSSESSION"):
                console.verify_response(json.loads(invite.read_text()),edited)
    def test_no_duplicate_invite_overwrites_existing_request(self):
        with tempfile.TemporaryDirectory() as d:
            console.invite(d,"reviewer123","owner")
            with self.assertRaises(FileExistsError):
                console.invite(d,"reviewer123","owner")
if __name__=="__main__":unittest.main()
