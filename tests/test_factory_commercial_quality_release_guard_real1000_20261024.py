#!/usr/bin/env python3
"""Adversarial QC release test: self-scored '1000' without real executions is blocked."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
GUARD=ROOT/"scripts/factory_commercial_quality_release_guard_v1.py"

def load_guard():
    spec=importlib.util.spec_from_file_location("commercial_qc_guard",str(GUARD))
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

class ReleaseMustHaveRealExecutionReceipts(unittest.TestCase):
    def test_old_editions_never_receive_qc1000(self):
        gate=load_guard()
        row=gate.require_quality_clearance("/dev/null","some_product","a"*64,
             {"professional_quality_standard":"legacy"},"/dev/null")
        self.assertIs(row["1000_quality_verified"],False)

    def test_forged_report_and_four_claimed_signers_still_block_without_executions(self):
        gate=load_guard()
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            inbox=base/"private"
            archive=base/"product.zip"
            archive.write_bytes(b"not a certified package")
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            pkg=inbox/"quality-clearance"/"test_product"/digest
            pkg.mkdir(parents=True)
            trust=inbox/"quality-trust"
            trust.mkdir()
            (pkg/"signed-1000.json").write_text(json.dumps({"decision":{"100_groups":{
                "Q%03d"%i:10 for i in range(1,101)}}}))
            (pkg/"global-premium-report.json").write_text("{}")
            (pkg/"quality-100-groups.json").write_text("{}")
            (trust/"trusted-reviewers.json").write_text("{}")
            # Test-only stub pretends that an earlier signature check accepted
            # the full 100x10 grade; the new gate MUST still reject it.
            (base/"factory_quality_signed_approval_v1.py").write_text(
                "def inspect_approval(*args):\n"
                "    import hashlib\n"
                "    return {'eligible':True,'artifact_sha256':"
                "hashlib.sha256(open(args[2],'rb').read()).hexdigest(),"
                "'verifiable_reviewer_count':4}\n"
            )
            original=gate.__file__
            gate.__file__=str(base/"factory_commercial_quality_release_guard_v1.py")
            try:
                with self.assertRaisesRegex(ValueError,
                       "QC1000_TRUSTED_REAL_EXECUTION_EVIDENCE_MISSING"):
                    gate.require_quality_clearance(inbox,"test_product",digest,
                        {"professional_quality_standard":"100_groups_x_10"},archive)
            finally:
                gate.__file__=original

    def test_missing_signature_bound_to_exact_executed_dossier_is_rejected(self):
        gate=load_guard()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            container=root/"quality-clearance"/"item"/("a"*64)
            container.mkdir(parents=True)
            trust=root/"quality-trust"
            trust.mkdir()
            (container/"real-qc1000-suite.json").write_text('{"cases":[]}')
            (container/"doctoral-dossier.json").write_text("{}")
            pub=trust/"trusted-execution-runner-rsa3072.pem"
            pub.write_bytes(b"fake public key")
            module=ROOT/"scripts/factory_real_qc1000_live_monitor_20261023.py"
            self.assertTrue(module.exists())
            # Even a matching SHA of an attacker-chosen key is not enough to
            # bypass the independent decision-to-suite digest requirement.
            env="FACTORY_QC1000_TRUSTED_RUNNER_PUBKEY_SHA256"
            old=os.environ.get(env)
            os.environ[env]=hashlib.sha256(pub.read_bytes()).hexdigest()
            try:
                with self.assertRaisesRegex(ValueError,
                      "QC1000_SIGNED_DECISION_NOT_BOUND_TO_EXECUTED_EVIDENCE"):
                    gate._verify_executed_qc1000(root,container,"a"*64,{})
            finally:
                if old is None:os.environ.pop(env,None)
                else:os.environ[env]=old

if __name__=="__main__":
    unittest.main()
