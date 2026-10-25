"""Offline production probe contract checks; no live RPC, wallets or purchases."""
import unittest
from dataclasses import replace
from datetime import datetime, timezone

from scripts.mpw_tron_dual_provider_auth_readonly_20261022 import audit
from services.mpw_trx_walletless_core import SolidifiedTransfer


NOW=datetime(2026,10,22,6,tzinfo=timezone.utc)
TXID="a"*64
SENDER="T"+"a"*33
RECEIVER="T"+"b"*33


def credentials():
    return {
        "MPW_TRON_RPC_INDEPENDENCE_REVIEWED":"1",
        "MPW_TRON_RPC_A_SOURCE_ID":"trongrid-mainnet",
        "MPW_TRON_RPC_A_OPERATOR_ID":"tron-grid",
        "MPW_TRON_RPC_A_ENDPOINT":"https://api.trongrid.io",
        "MPW_TRON_RPC_A_API_KEY":"test-a-secret",
        "MPW_TRON_RPC_A_AUTH_HEADER":"TRON-PRO-API-KEY",
        "MPW_TRON_RPC_B_SOURCE_ID":"nodit-mainnet",
        "MPW_TRON_RPC_B_OPERATOR_ID":"nodit",
        "MPW_TRON_RPC_B_ENDPOINT":"https://tron-mainnet.nodit.io",
        "MPW_TRON_RPC_B_API_KEY":"test-b-secret",
        "MPW_TRON_RPC_B_AUTH_HEADER":"X-API-KEY",
        "MPW_TRON_RPC_CANARY_TXID":TXID,
        "MPW_TRON_RPC_CANARY_SENDER":SENDER,
        "MPW_TRON_RPC_CANARY_RECEIVER":RECEIVER,
        "MPW_TRON_RPC_CANARY_AMOUNT_SUN":"123456",
    }


def receipt(provider,_txid):
    return SolidifiedTransfer(provider.source_id,TXID,"tron-mainnet",RECEIVER,SENDER,
                             123456,NOW,True,True,True)


class ProbeContractTests(unittest.TestCase):
    def execute(self,env,**overrides):
        probes=dict(now=NOW,head_probe=lambda _provider,now: 70000000,
                    transfer_probe=receipt)
        probes.update(overrides)
        return audit(env,**probes)

    def test_configured_distinct_authenticated_proofs_are_not_live_checkout(self):
        outcome=self.execute(credentials())
        self.assertEqual(outcome["status"],"PROVIDER_PROOF_READY_ONLY")
        self.assertTrue(outcome["two_fresh_solidified_heads"])
        self.assertTrue(outcome["matching_native_transfer_body_and_receipts"])
        self.assertEqual(outcome["financial_writes"],0)
        self.assertFalse(outcome["public_payment_activated"])
        self.assertNotIn("test-a-secret",str(outcome))

    def test_unattested_and_reused_operator_fail_closed(self):
        env=credentials()
        env.pop("MPW_TRON_RPC_INDEPENDENCE_REVIEWED")
        self.assertEqual(self.execute(env)["reason"],"independent_operator_review_missing")
        env=credentials()
        env["MPW_TRON_RPC_B_OPERATOR_ID"]=env["MPW_TRON_RPC_A_OPERATOR_ID"]
        self.assertEqual(self.execute(env)["reason"],"provider_configuration_unapproved")

    def test_missing_key_and_wrong_nodit_auth_header_fail_closed(self):
        for field,bad in (("MPW_TRON_RPC_B_API_KEY",""),
                          ("MPW_TRON_RPC_B_AUTH_HEADER","TRON-PRO-API-KEY")):
            with self.subTest(field=field):
                env=credentials()
                env[field]=bad
                self.assertEqual(self.execute(env)["reason"],"provider_configuration_unapproved")

    def test_node_unavailable_is_not_reported_as_verified(self):
        result=self.execute(credentials(),head_probe=lambda _p,now: 0)
        self.assertEqual(result["reason"],"authenticated_solidified_head_unavailable")
        self.assertFalse(result["matching_native_transfer_body_and_receipts"])

    def test_no_known_mainnet_canary_is_not_verified(self):
        env=credentials()
        env["MPW_TRON_RPC_CANARY_TXID"]=""
        self.assertEqual(self.execute(env)["reason"],"verified_native_canary_missing")

    def test_independent_proof_mismatch_cannot_pass(self):
        for difference in ("amount_sun","source_id","sender","block_time","execution_success"):
            def tampered(provider,_txid):
                original=receipt(provider,_txid)
                if provider.source_id!="nodit-mainnet":
                    return original
                bad={"amount_sun":1,"source_id":"trongrid-mainnet","sender":"not-owner",
                     "block_time":NOW.replace(second=1),"execution_success":False}
                return replace(original,**{difference:bad[difference]})
            with self.subTest(difference=difference):
                self.assertEqual(self.execute(credentials(),transfer_probe=tampered)["reason"],
                                 "independent_native_transaction_proof_failed")


if __name__=="__main__":unittest.main()
