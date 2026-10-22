"""F41 mainnet verifier adversarial fixture tests, with no real RPC or money."""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import f41_merchant_audit_cli as audit
import f41_tron_mainnet_check as check

RECIPIENT = "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"
TOKEN = "TWTBsKZPVuQgaGNbyJWJm9XR28g4wVBCNQ"
TXID = "a" * 64


def as_csv(header, entries):
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(entries)
    return out.getvalue().encode("utf8")


def samples(asset="TRX", network="tron-mainnet", recipient=RECIPIENT, amount="1000000"):
    contract = TOKEN if asset == "TRC20" else ""
    inv = ["I001", network, asset, recipient, amount, contract]
    obs = ["I001", TXID, network, asset, recipient, amount, contract]
    return as_csv(audit.INV_FIELDS, [inv]), as_csv(audit.PAY_FIELDS, [obs])


def trx_body(amount=1000000, recipient=RECIPIENT, txid=TXID):
    return {
        "txID": txid, "ret": [{"contractRet": "SUCCESS"}],
        "raw_data": {"contract": [{"type": "TransferContract",
                  "parameter": {"value": {"to_address": check.tron_hex(recipient),
                                          "amount": amount}}}]}
    }


def token_body(txid=TXID):
    return {"txID": txid, "ret": [{"contractRet": "SUCCESS"}],
            "raw_data": {"contract": [{"type": "TriggerSmartContract"}]}}


def token_receipt(amount=1000000, recipient=RECIPIENT, contract=TOKEN, txid=TXID):
    return {
        "id": txid, "blockNumber": 12345, "receipt": {"result": "SUCCESS"},
        "log": [{"address": check.tron_hex(contract)[2:],
                 "topics": [check.TOPIC_TRANSFER, "0"*24+"1"*40,
                            "0"*24+check.tron_hex(recipient)[2:]],
                 "data": ("%064x" % amount)}]
    }


class MainnetSecurityTests(unittest.TestCase):
    def test_trx_body_exact_solidified(self):
        inv = {"recipient": RECIPIENT, "amount_base_units": "1000000"}
        self.assertEqual(check.check_trx(inv, TXID, trx_body()), ("TRX_SOLIDIFIED_NODE_MATCH", True))

    def test_trx_wrong_amount_fails(self):
        inv = {"recipient": RECIPIENT, "amount_base_units": "1000000"}
        self.assertFalse(check.check_trx(inv, TXID, trx_body(amount=1000001))[1])

    def test_trx_wrong_recipient_fails(self):
        inv = {"recipient": TOKEN, "amount_base_units": "1000000"}
        self.assertFalse(check.check_trx(inv, TXID, trx_body())[1])

    def test_trx_wrong_txid_fails(self):
        inv = {"recipient": RECIPIENT, "amount_base_units": "1000000"}
        self.assertFalse(check.check_trx(inv, TXID, trx_body(txid="b"*64))[1])

    def test_failed_body_and_wrong_contract_rejected(self):
        inv = {"recipient": RECIPIENT, "amount_base_units": "1000000"}
        p = trx_body()
        p["ret"][0]["contractRet"] = "FAILED"
        self.assertFalse(check.check_trx(inv, TXID, p)[1])
        p = trx_body()
        p["raw_data"]["contract"][0]["type"] = "TriggerSmartContract"
        self.assertFalse(check.check_trx(inv, TXID, p)[1])

    def test_trc20_exact_approved_event(self):
        inv = {"recipient": RECIPIENT, "amount_base_units": "1000000"}
        status, yes = check.check_token(inv, TXID, token_body(), token_receipt(), check.tron_hex(TOKEN))
        self.assertTrue(yes)
        self.assertEqual(status, "TRC20_SOLIDIFIED_NODE_MATCH")

    def test_trc20_wrong_contract_recipient_amount(self):
        inv = {"recipient": RECIPIENT, "amount_base_units": "1000000"}
        for receipt in [token_receipt(contract=RECIPIENT),
                        token_receipt(recipient=TOKEN),
                        token_receipt(amount=1000001)]:
            self.assertFalse(check.check_token(
                inv, TXID, token_body(), receipt, check.tron_hex(TOKEN))[1])

    def test_trc20_failed_receipt(self):
        inv = {"recipient": RECIPIENT, "amount_base_units": "1000000"}
        p = token_receipt()
        p["receipt"]["result"] = "FAILED"
        self.assertFalse(check.check_token(inv, TXID, token_body(), p, check.tron_hex(TOKEN))[1])

    def test_trc20_duplicate_matching_logs_fails(self):
        inv = {"recipient": RECIPIENT, "amount_base_units": "1000000"}
        p = token_receipt()
        p["log"].append(p["log"][0])
        self.assertFalse(check.check_token(inv, TXID, token_body(), p, check.tron_hex(TOKEN))[1])

    def test_no_actual_rpc_for_shasta_only(self):
        i, p = samples(network="shasta")
        def never(_):
            raise AssertionError("unexpected live mainnet RPC")
        result = check.evaluate(i, p, lookup=never, receipt_lookup=never, tokens=set())
        self.assertEqual(result["network_lookups_attempted"], 0)
        self.assertEqual(result["live_matched_count"], 0)

    def test_export_match_is_never_live_proof_under_mock(self):
        i, p = samples()
        result = check.evaluate(i, p, lookup=lambda _: trx_body(),
                                receipt_lookup=lambda _: {}, tokens=set())
        self.assertEqual(result["records"][0]["status"], "SIMULATED_MATCH_NOT_LIVE_EVIDENCE")
        self.assertTrue(result["records"][0]["node_payload_matches_invoice"])
        self.assertFalse(result["records"][0]["live_solidified_node_evidence"])
        self.assertFalse(result["customer_delivery_authorized"])

    def test_operator_contract_approval_required(self):
        i, p = samples(asset="TRC20")
        def never(_):
            raise AssertionError("unapproved TRC20 never calls network")
        result = check.evaluate(i, p, lookup=never, receipt_lookup=never, tokens=set())
        self.assertEqual(result["records"][0]["status"], "TOKEN_CONTRACT_NOT_OPERATOR_APPROVED")
        self.assertEqual(result["network_lookups_attempted"], 0)

    def test_mock_trc20_match_not_live_proof(self):
        i, p = samples(asset="TRC20")
        result = check.evaluate(i, p, lookup=lambda _: token_body(),
                                receipt_lookup=lambda _: token_receipt(),
                                tokens={check.tron_hex(TOKEN)})
        self.assertTrue(result["records"][0]["node_payload_matches_invoice"])
        self.assertFalse(result["records"][0]["live_solidified_node_evidence"])
        self.assertEqual(result["network_lookups_attempted"], 2)

    def test_rpc_errors_fail_closed(self):
        i, p = samples()
        def fail(_):
            raise OSError("offline")
        result = check.evaluate(i, p, lookup=fail, receipt_lookup=fail, tokens=set())
        self.assertEqual(result["records"][0]["status"], "MAINNET_NODE_UNAVAILABLE_OR_INVALID")
        self.assertEqual(result["live_matched_count"], 0)

    def test_unapproved_endpoint_rejected_without_network(self):
        with self.assertRaisesRegex(ValueError, "NOT_APPROVED"):
            check.rpc(TXID, "https://example.org/walletsolidity/gettransactionbyid")

    def test_query_budget_fail_closed(self):
        inv, pay = [], []
        for number in range(11):
            ident = "I%03d" % number
            inv.append([ident, "tron-mainnet", "TRX", RECIPIENT, "1", ""])
            pay.append([ident, "%064x" % (number + 1), "tron-mainnet", "TRX", RECIPIENT, "1", ""])
        i = as_csv(audit.INV_FIELDS, inv)
        p = as_csv(audit.PAY_FIELDS, pay)
        with self.assertRaisesRegex(ValueError, "BUDGET_EXCEEDED"):
            check.evaluate(i, p, lookup=lambda _: trx_body(), tokens=set())

    def test_private_zero_rpc_report_is_explicit(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            i, p = samples(network="shasta")
            (root/"invoices.csv").write_bytes(i)
            (root/"payments.csv").write_bytes(p)
            result = check.write_private(root/"invoices.csv", root/"payments.csv", root/"evidence")
            self.assertEqual(result["network_lookups_attempted"], 0)
            self.assertFalse(result["simulation"])
            stored = json.loads((root/"evidence"/"node-evidence.json").read_text("utf8"))
            self.assertEqual(stored["live_matched_count"], 0)
            self.assertFalse(stored["customer_delivery_authorized"])
            self.assertTrue((root/"evidence"/"integrity.json").is_file())


if __name__ == "__main__":
    unittest.main()
