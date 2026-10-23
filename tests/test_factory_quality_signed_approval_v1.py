"""Behavioral negative and positive controls for real OpenSSL Ed25519 approvals.

Ephemeral test keys only. Never ship test signatures as production authority.
"""
import hashlib,importlib.util,json,subprocess,tempfile
from unittest.mock import patch
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/factory_quality_signed_approval_v1.py"
spec=importlib.util.spec_from_file_location("signed_approval",SCRIPT)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
ROLES=mod.ROLES

class SignedApprovalTests(unittest.TestCase):
    def make(self,d):
        root=Path(d)
        build=root/"real-build.zip";build.write_bytes(b"versioned product ZIP"+bytes(range(128)))
        cat=root/"catalog.json";cat.write_text("one hundred criteria x ten points")
        decision={"artifact_sha256":mod.digest(build),
                  "quality_catalog_sha256":mod.digest(cat),
                  "family_id":"F14","unresolved_critical_defects":0,
                  "evidence_manifest_sha256":"a"*64,
                  "100_groups":{"Q%03d"%n:10 for n in range(1,101)}}
        gate={"schema":"saeit.factory.global-premium-quality.v1",
              "family_id":"F14","technical_test_passed":True,
              "blockers":[{"code":"P0_INDEPENDENT_ATTESTATION_NOT_AUTHENTICATED"},
                          {"code":"P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED"}]}
        decision["gate_report_sha256"]=hashlib.sha256(mod.canonical(gate)).hexdigest()
        trust={"schema":mod.KEY_SCHEMA,"reviewers":{}}
        sigs=[]
        for role in ROLES:
            reviewer="trusted_"+role
            priv=root/(reviewer+".pem")
            pub=root/(reviewer+".pub.pem")
            signature=root/(reviewer+".signature.bin")
            subprocess.run(["openssl","genpkey","-algorithm","ED25519","-out",str(priv)],
                           check=True,capture_output=True)
            with pub.open("wb") as f:
                subprocess.run(["openssl","pkey","-in",str(priv),"-pubout"],
                               check=True,stdout=f,stderr=subprocess.PIPE)
            data=root/"decision.bin";data.write_bytes(mod.canonical(decision))
            subprocess.run(["openssl","pkeyutl","-sign","-rawin","-inkey",str(priv),
                            "-in",str(data),"-out",str(signature)],check=True,capture_output=True)
            trust["reviewers"][reviewer]={"role":role,"public_key_pem":pub.read_text(),
                                        "externally_identity_verified":True}
            sigs.append({"reviewer_id":reviewer,"role":role,
                         "signature_hex":signature.read_bytes().hex()})
        authority_priv=root/"authorized-owner-root.pem"
        authority_pub=root/"authorized-owner-root.pub.pem"
        authority_sig=root/"root-registry.sig"
        subprocess.run(["openssl","genpkey","-algorithm","ED25519","-out",str(authority_priv)],
                       check=True,capture_output=True)
        with authority_pub.open("wb") as f:
            subprocess.run(["openssl","pkey","-in",str(authority_priv),"-pubout"],
                           check=True,stdout=f,stderr=subprocess.PIPE)
        for entry in trust["reviewers"].values():
            entry["identity_verification_evidence_sha256"]="e"*64
            entry["active"]=True
        root_data=root/"registry-content.bin"
        root_data.write_bytes(mod.canonical({"schema":mod.KEY_SCHEMA,"reviewers":trust["reviewers"]}))
        subprocess.run(["openssl","pkeyutl","-sign","-rawin",
                        "-inkey",str(authority_priv),"-in",str(root_data),
                        "-out",str(authority_sig)],check=True,capture_output=True)
        trust["trusted_root_public_key_pem"]=authority_pub.read_text()
        trust["root_signature_hex"]=authority_sig.read_bytes().hex()
        return root,build,cat,decision,gate,trust,sigs
    def check(self,x):
        root,build,cat,decision,gate,trust,sigs=x
        with patch.dict("os.environ",{"FACTORY_QA_TRUST_ROOT_SHA256":hashlib.sha256(trust.get("trusted_root_public_key_pem","").encode()).hexdigest()}):
            return mod.inspect_approval({"schema":mod.SCHEMA,"decision":decision,
                  "approvals":sigs},gate,build,cat,trust)
    def make_delegated(self,d):
        """Synthetic cryptographic authority; does not represent a real owner/expert."""
        x=list(self.make(d))
        root,_,_,decision,_,trust,sigs=x
        del trust["reviewers"]["trusted_owner"]
        sigs[:]=[v for v in sigs if v["role"]!="owner"]
        agent_priv=root/"delegate.private.pem"
        agent_pub=root/"delegate.public.pem"
        subprocess.run(["openssl","genpkey","-algorithm","ED25519","-out",str(agent_priv)],
                       check=True,capture_output=True)
        with agent_pub.open("wb") as f:
            subprocess.run(["openssl","pkey","-in",str(agent_priv),"-pubout"],
                           check=True,stdout=f,stderr=subprocess.PIPE)
        owner_priv=root/"authorized-owner-root.pem"
        owner_pub=root/"authorized-owner-root.pub.pem"
        from datetime import datetime,timedelta,timezone
        now=datetime.now(timezone.utc)
        grant={"schema":mod.DELEGATION_SCHEMA,"reviewer_id":"factory_agent_moj1",
               "agent_public_key_sha256":hashlib.sha256(agent_pub.read_bytes()).hexdigest(),
               "owner_root_public_key_sha256":hashlib.sha256(owner_pub.read_bytes()).hexdigest(),
               "scope":mod.DELEGATION_SCOPE,"authorized_family_ids":["F14"],
               "not_before_utc":(now-timedelta(minutes=1)).isoformat(),
               "expires_at_utc":(now+timedelta(days=30)).isoformat()}
        def signed_by(key,payload):
            path=root/"payload.bin";sig=root/"sig.bin"
            path.write_bytes(mod.canonical(payload))
            subprocess.run(["openssl","pkeyutl","-sign","-rawin","-inkey",str(key),
                            "-in",str(path),"-out",str(sig)],check=True,capture_output=True)
            return sig.read_bytes().hex()
        trust["reviewers"]["factory_agent_moj1"]={
            "reviewer_id":"factory_agent_moj1",
            "role":mod.DELEGATE_ROLE,
            "public_key_pem":agent_pub.read_text(),
            "identity_verification_evidence_sha256":"b"*64,
            "externally_identity_verified":False,
            "agent_identity_verified":True,"active":True,
            "owner_delegation":grant,
            "owner_delegation_signature_hex":signed_by(owner_priv,grant)}
        trust["root_signature_hex"]=signed_by(owner_priv,{"schema":mod.KEY_SCHEMA,
                                                           "reviewers":trust["reviewers"]})
        sigs.append({"reviewer_id":"factory_agent_moj1","role":mod.DELEGATE_ROLE,
                     "signature_hex":signed_by(agent_priv,decision)})
        return x,owner_priv,signed_by

    def test_real_root_signed_scoped_agent_may_replace_owner_signoff_but_not_experts(self):
        with tempfile.TemporaryDirectory() as d:
            x,_,_=self.make_delegated(d)
            v=self.check(x)
            self.assertTrue(v["eligible"],v["blocking_reasons"])
            self.assertEqual(v["owner_authorization_kind"],"verified_delegated_agent")
            self.assertTrue(v["agent_not_a_human_expert"])
            self.assertEqual(len(v["valid_signed_roles"]),4)
            self.assertFalse(v["publication_executed"])

    def test_agent_with_correct_signature_but_wrong_product_scope_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            x,root_priv,sign=self.make_delegated(d)
            grant=x[5]["reviewers"]["factory_agent_moj1"]["owner_delegation"]
            grant["authorized_family_ids"]=["F28"]
            x[5]["reviewers"]["factory_agent_moj1"]["owner_delegation_signature_hex"]=sign(root_priv,grant)
            x[5]["root_signature_hex"]=sign(root_priv,{"schema":mod.KEY_SCHEMA,
                                                        "reviewers":x[5]["reviewers"]})
            self.assertIn("OWNER_AGENT_DELEGATION_SCOPE_VIOLATION",
                          self.check(x)["blocking_reasons"])

    def test_unsigned_agent_certificate_must_not_pass_root_registry(self):
        with tempfile.TemporaryDirectory() as d:
            x,root_priv,sign=self.make_delegated(d)
            x[5]["reviewers"]["factory_agent_moj1"]["owner_delegation"]["scope"]="unrestricted"
            x[5]["root_signature_hex"]=sign(root_priv,{"schema":mod.KEY_SCHEMA,
                                                        "reviewers":x[5]["reviewers"]})
            self.assertIn("TRUST_REGISTRY_INVALID",self.check(x)["blocking_reasons"])

    def test_agent_never_replaces_one_of_three_independent_humans(self):
        with tempfile.TemporaryDirectory() as d:
            x,_,_=self.make_delegated(d)
            x[6]=[sig for sig in x[6] if sig["role"]!="domain_specialist"]
            self.assertIn("MISSING_INDEPENDENT_SIGNED_ROLE:domain_specialist",
                          self.check(x)["blocking_reasons"])

    def test_owner_agent_delegation_date_window_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            x,owner_priv,sign=self.make_delegated(d)
            from datetime import datetime,timedelta,timezone
            grant=x[5]["reviewers"]["factory_agent_moj1"]["owner_delegation"]
            now=datetime.now(timezone.utc)
            grant["not_before_utc"]=(now-timedelta(days=4)).isoformat()
            grant["expires_at_utc"]=(now-timedelta(days=2)).isoformat()
            x[5]["reviewers"]["factory_agent_moj1"]["owner_delegation_signature_hex"]=sign(owner_priv,grant)
            x[5]["root_signature_hex"]=sign(owner_priv,{"schema":mod.KEY_SCHEMA,
                                                        "reviewers":x[5]["reviewers"]})
            self.assertIn("TRUST_REGISTRY_INVALID",self.check(x)["blocking_reasons"])

    def test_truly_signed_multirole_exact_version_allows_clearance_only(self):
        with tempfile.TemporaryDirectory() as d:
            v=self.check(self.make(d))
            self.assertTrue(v["eligible"],v["blocking_reasons"])
            self.assertEqual(v["verified_grade_total"],1000)
            self.assertEqual(len(v["valid_signed_roles"]),4)
            self.assertFalse(v["publication_executed"])
            self.assertFalse(v["payment_activated"])
    def test_no_registered_human_reviewer_cannot_self_approve(self):
        with tempfile.TemporaryDirectory() as d:
            x=list(self.make(d));x[5]={"schema":mod.KEY_SCHEMA,"reviewers":{}}
            v=self.check(x)
            self.assertFalse(v["eligible"])
            self.assertIn("TRUST_REGISTRY_INVALID",v["blocking_reasons"])
    def test_wrong_build_hash_fails_even_if_four_signatures_are_valid(self):
        with tempfile.TemporaryDirectory() as d:
            x=self.make(d);x[1].write_bytes(x[1].read_bytes()+b"tampered")
            v=self.check(x)
            self.assertIn("DECISION_WRONG_BUILD_VERSION",v["blocking_reasons"])
    def test_changed_scores_or_rights_break_signature(self):
        with tempfile.TemporaryDirectory() as d:
            x=list(self.make(d));x[3]["100_groups"]["Q024"]=9
            v=self.check(x)
            self.assertFalse(v["eligible"])
            self.assertIn("NOT_ALL_100_GROUPS_INDEPENDENTLY_GRADED_TEN",v["blocking_reasons"])
            self.assertIn("INVALID_APPROVAL_SIGNATURE",v["blocking_reasons"])
    def test_one_unresolved_domain_error_blocks_all_four_valid_signatures(self):
        with tempfile.TemporaryDirectory() as d:
            x=list(self.make(d))
            x[4]["blockers"].append({"code":"P0_DOMAIN_SPECIALIST_PROOF_MISSING:peer_review"})
            v=self.check(x)
            self.assertIn("SUBSTANTIVE_QUALITY_GAPS_REMAIN",v["blocking_reasons"])
            self.assertFalse(v["eligible"])
    def test_missing_owner_signature_blocks_commercial_clearance(self):
        with tempfile.TemporaryDirectory() as d:
            x=list(self.make(d));x[6]=x[6][:-1]
            v=self.check(x)
            self.assertIn("MISSING_INDEPENDENT_SIGNED_ROLE:owner",v["blocking_reasons"])
    def test_one_person_cannot_be_four_independent_roles(self):
        with tempfile.TemporaryDirectory() as d:
            x=list(self.make(d));x[6][1]["reviewer_id"]=x[6][0]["reviewer_id"]
            v=self.check(x)
            self.assertIn("DUPLICATED_REVIEWER_IDENTITY",v["blocking_reasons"])
    def test_signature_without_externally_verified_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            x=list(self.make(d));x[5]["reviewers"]["trusted_domain_specialist"]["externally_identity_verified"]=False
            v=self.check(x)
            self.assertIn("TRUST_REGISTRY_INVALID",v["blocking_reasons"])
    def test_legacy_self_approval_field_does_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            x=list(self.make(d));x[3]["self_approved"]=True
            v=self.check(x)
            self.assertFalse(v["eligible"])
            self.assertIn("INVALID_APPROVAL_SIGNATURE",v["blocking_reasons"])
    def test_changing_registry_key_without_owner_root_resign_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            x=list(self.make(d))
            x[5]["reviewers"]["trusted_owner"]["identity_verification_evidence_sha256"]="a"*64
            v=self.check(x)
            self.assertFalse(v["eligible"])
            self.assertIn("TRUST_REGISTRY_INVALID",v["blocking_reasons"])
    def test_no_server_pinned_trust_root_rejects_even_genuine_signatures(self):
        with tempfile.TemporaryDirectory() as d:
            root,build,cat,decision,gate,trust,sigs=self.make(d)
            with patch.dict("os.environ",{"FACTORY_QA_TRUST_ROOT_SHA256":""}):
                v=mod.inspect_approval({"schema":mod.SCHEMA,"decision":decision,
                    "approvals":sigs},gate,build,cat,trust)
            self.assertIn("TRUST_REGISTRY_INVALID",v["blocking_reasons"])
if __name__=="__main__":unittest.main()
