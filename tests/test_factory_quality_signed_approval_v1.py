"""Behavioral negative and positive controls for real OpenSSL Ed25519 approvals.

Ephemeral test keys only. Never ship test signatures as production authority.
"""
import hashlib,importlib.util,json,subprocess,tempfile
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
        return root,build,cat,decision,gate,trust,sigs
    def check(self,x):
        root,build,cat,decision,gate,trust,sigs=x
        return mod.inspect_approval({"schema":mod.SCHEMA,"decision":decision,
                  "approvals":sigs},gate,build,cat,trust)
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
            self.assertIn("MISSING_INDEPENDENT_SIGNED_ROLE:owner",v["blocking_reasons"])
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
if __name__=="__main__":unittest.main()
