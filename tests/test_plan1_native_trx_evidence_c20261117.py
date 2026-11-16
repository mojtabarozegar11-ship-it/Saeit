"""Cycle C: adversarial tests for real funded Plan 1 evidence, no payment."""
import copy
import unittest
from prop_firm.plan1_native_trx_evidence import (
    verify_native_plan1_transfer, ProofRejected, AMOUNT_SUN,
)

TX = "a" * 64
OWNER = "41" + "b" * 40
SENDER = "41" + "c" * 40


def fixture():
    order = dict(sku="MOJ-PROP-01", network="TRON-mainnet", amount_sun=AMOUNT_SUN,
                 order_ref="ORDER-1", enrollment_ref="ENROLL-1", terms_version="v1.2",
                 recipient_hex=OWNER, txid=TX)
    transaction = dict(txID=TX, raw_data=dict(contract=[dict(
        type="TransferContract", parameter=dict(value=dict(
            amount=AMOUNT_SUN, to_address=OWNER, owner_address=SENDER)))]),
        ret=[dict(contractRet="SUCCESS")])
    info = dict(id=TX, blockNumber=123, fee=0, receipt=dict(result="SUCCESS"))
    attest = dict(network="TRON-mainnet", source="independent-solidity-node",
                  txid=TX, block_number=123, block_id="d"*64,
                  solidified=True, authenticated=True, genesis_verified=True,
                  transaction_endpoint="/walletsolidity/gettransactionbyid",
                  receipt_endpoint="/walletsolidity/gettransactioninfobyid")
    return dict(order=order, owner_receiver_hex=OWNER, transaction=transaction,
                transaction_info=info, attestation=attest)


class Plan1NativeTRXProofTests(unittest.TestCase):
    def test_positive_is_evidence_only(self):
        result = verify_native_plan1_transfer(**fixture())
        self.assertEqual(result.amount_sun, 30_000_000)
        self.assertEqual(result.state, "SOLIDIFIED_EVIDENCE_ONLY")
        self.assertFalse(result.payable or result.credited or result.receipt_issued
                         or result.enrollment_activated)
        self.assertEqual(len(result.evidence_sha256), 64)

    def test_adversarial_mutations_rejected(self):
        cases = [
            ("wrong sku", ("order", "sku"), "MOJPROP-STARTER30"),
            ("wrong chain", ("order", "network"), "TRON-Shasta"),
            ("amount", ("order", "amount_sun"), 29_999_999),
            ("boolean amount", ("order", "amount_sun"), True),
            ("wrong receiver", ("order", "recipient_hex"), SENDER),
            ("wrong txid", ("order", "txid"), "A"*64),
            ("wrong tx record", ("transaction", "txID"), "e"*64),
            ("no raw data", ("transaction", "raw_data"), None),
            ("missing receipt", ("transaction_info", "id"), ""),
            ("failed receipt", ("transaction_info", "receipt", "result"), "REVERT"),
            ("wrong block", ("transaction_info", "blockNumber"), 122),
            ("negative fee", ("transaction_info", "fee"), -1),
            ("wrong source", ("attestation", "source"), "browser"),
            ("not solidified", ("attestation", "solidified"), False),
            ("not authenticated", ("attestation", "authenticated"), False),
            ("genesis not verified", ("attestation", "genesis_verified"), False),
            ("wrong node network", ("attestation", "network"), "Nile"),
            ("wrong node tx", ("attestation", "txid"), "e"*64),
            ("wrong block hash", ("attestation", "block_id"), "invalid"),
            ("wrong block number", ("attestation", "block_number"), 122),
            ("wrong tx endpoint", ("attestation", "transaction_endpoint"), "/wallet/gettransactionbyid"),
            ("wrong info endpoint", ("attestation", "receipt_endpoint"), "/wallet/gettransactioninfobyid"),
            ("wrong transfer type", ("transaction", "raw_data", "contract", 0, "type"), "TriggerSmartContract"),
            ("wrong transfer amount", ("transaction", "raw_data", "contract", 0, "parameter", "value", "amount"), 30_000_001),
            ("wrong destination", ("transaction", "raw_data", "contract", 0, "parameter", "value", "to_address"), SENDER),
            ("self transfer", ("transaction", "raw_data", "contract", 0, "parameter", "value", "owner_address"), OWNER),
            ("execution failed", ("transaction", "ret", 0, "contractRet"), "REVERT"),
            ("wrong owner binding", ("owner_receiver_hex",), SENDER),
            ("no enrollment", ("order", "enrollment_ref"), ""),
            ("no terms", ("order", "terms_version"), ""),
        ]
        for label, path, value in cases:
            with self.subTest(label=label):
                data = copy.deepcopy(fixture())
                obj = data
                for key in path[:-1]:
                    obj = obj[key]
                obj[path[-1]] = value
                with self.assertRaises(ProofRejected):
                    verify_native_plan1_transfer(**data)

    def test_empty_solidity_responses_never_count_as_payment(self):
        for key in ("transaction", "transaction_info", "attestation"):
            data = fixture()
            data[key] = {}
            with self.subTest(key=key), self.assertRaises(ProofRejected):
                verify_native_plan1_transfer(**data)

    def test_two_native_contracts_are_not_single_exact_transfer(self):
        data = fixture()
        data["transaction"]["raw_data"]["contract"].append(
            copy.deepcopy(data["transaction"]["raw_data"]["contract"][0]))
        with self.assertRaises(ProofRejected):
            verify_native_plan1_transfer(**data)


if __name__ == "__main__":
    unittest.main()
