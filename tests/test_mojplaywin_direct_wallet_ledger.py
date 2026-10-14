"""Isolated SQLite order and chain settlement tests; all RPCs are simulated."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import mojplaywin_direct_wallet_invoice as inv
import mojplaywin_direct_wallet_ledger as ledger
from mojplaywin_native_chain_verify import tron_address_to_hex

START=1_700_000_000
ETH_HASH="0x"+"a"*64
TRON_HASH="b"*64
ETH_SENDER="0x"+"d"*40
TRON_SENDER=inv.NETWORKS["TRX"]["recipient"]

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file=Path(self.temp.name)/"wallet/ledger.sqlite3"
        self.book=ledger.StagingLedger(self.file)
        self.book.initialize()

    def invoice(self,order=9001,asset="ETH",units=2500000000000000):
        return inv.DirectInvoice(
            order_id=order,product_id=72,customer_id=48,
            asset=asset,chain=inv.NETWORKS[asset]["chain"],
            recipient=inv.NETWORKS[asset]["recipient"],
            expected_sender=ETH_SENDER if asset=="ETH" else TRON_SENDER,
            amount_smallest_units=units if asset=="ETH" else 25000000,
            quote_price_usd="7.50",quote_provider="coingecko",
            issued_at_epoch=START,expires_at_epoch=START+600,
            sender_proof_verified=True,
        )

    def eth_rpc(self, method,params):
        values={
          "eth_chainId":"0x1","eth_blockNumber":hex(111),
          "eth_getTransactionByHash":{
             "hash":ETH_HASH,"from":ETH_SENDER,"to":inv.NETWORKS["ETH"]["recipient"],
             "value":hex(2500000000000000),"blockNumber":hex(100),"blockHash":"0x"+"f"*64
          },
          "eth_getTransactionReceipt":{
             "transactionHash":ETH_HASH,"status":"0x1","blockNumber":hex(100),
             "blockHash":"0x"+"f"*64
          },
          "eth_getBlockByNumber":{"hash":"0x"+"f"*64,"timestamp":hex(START+20)}
        }
        return values[method]

    def tron_rpc(self,path,params):
        sender=tron_address_to_hex(TRON_SENDER)
        if path=="/walletsolidity/gettransactionbyid":
            return {"txID":TRON_HASH,"ret":[{"contractRet":"SUCCESS"}],
                    "raw_data":{"contract":[{"type":"TransferContract",
                      "parameter":{"value":{"owner_address":sender,
                                          "to_address":sender,"amount":25000000}}}]}}
        if path=="/walletsolidity/gettransactioninfobyid":
            return {"id":TRON_HASH,"blockNumber":1000000,
                    "blockTimeStamp":(START+20)*1000,
                    "receipt":{"result":"SUCCESS"}}
        raise ValueError("unrecognized RPC")

    def test_register_persistent_invoice(self):
        self.assertEqual(self.book.register_invoice(self.invoice()),"awaiting")
        self.assertEqual(ledger.StagingLedger(self.file).get(9001)["status"],"awaiting")

    def test_duplicate_order_refused(self):
        self.book.register_invoice(self.invoice())
        with self.assertRaises(ledger.LedgerError):
            self.book.register_invoice(self.invoice())

    def test_same_amount_cannot_serve_two_orders(self):
        self.book.register_invoice(self.invoice())
        with self.assertRaises(ledger.LedgerError):
            self.book.register_invoice(self.invoice(order=9002))

    def test_different_amounts_are_allowed(self):
        self.book.register_invoice(self.invoice())
        self.book.register_invoice(self.invoice(order=9002,units=2500000000000001))
        self.assertEqual(self.book.get(9002)["status"],"awaiting")

    def test_rejects_unverified_sender(self):
        with self.assertRaises(ledger.LedgerError):
            self.book.register_invoice(replace(self.invoice(),sender_proof_verified=False))

    def test_rejects_wrong_price(self):
        with self.assertRaises(ledger.LedgerError):
            self.book.register_invoice(replace(self.invoice(),quote_price_usd="7.51"))

    def test_rejects_wrong_recipient(self):
        with self.assertRaises(ledger.LedgerError):
            self.book.register_invoice(replace(self.invoice(),recipient=ETH_SENDER))

    def test_eth_paid_after_verification(self):
        self.book.register_invoice(self.invoice())
        self.assertEqual(self.book.settle_verified_transfer(9001,ETH_HASH,ethereum_rpc=self.eth_rpc),
                         "paid_in_staging_only")
        self.assertEqual(self.book.get(9001)["status"],"paid")
        self.assertEqual(self.book.settle_verified_transfer(9001,ETH_HASH,ethereum_rpc=self.eth_rpc),
                         "already_paid")

    def test_cannot_pay_with_fake_hash(self):
        self.book.register_invoice(self.invoice())
        with self.assertRaises(ValueError):
            self.book.settle_verified_transfer(9001,"0x1234",ethereum_rpc=self.eth_rpc)
        self.assertEqual(self.book.get(9001)["status"],"awaiting")

    def test_rejects_wrong_amount_even_if_transaction_succeeds(self):
        self.book.register_invoice(self.invoice(units=2500000000000001))
        with self.assertRaises(ValueError):
            self.book.settle_verified_transfer(9001,ETH_HASH,ethereum_rpc=self.eth_rpc)
        self.assertEqual(self.book.get(9001)["status"],"awaiting")

    def test_never_settle_without_rpc(self):
        self.book.register_invoice(self.invoice())
        with self.assertRaises(ledger.LedgerError):
            self.book.settle_verified_transfer(9001,ETH_HASH)

    def test_trx_fully_verified(self):
        self.book.register_invoice(self.invoice(asset="TRX"))
        self.assertEqual(self.book.settle_verified_transfer(9001,TRON_HASH,
                  tron_solidity_rpc=self.tron_rpc),"paid_in_staging_only")

    def test_reused_chain_transaction_rejected_for_other_order(self):
        self.book.register_invoice(self.invoice())
        self.book.register_invoice(self.invoice(order=9002,units=2500000000000001))
        self.book.settle_verified_transfer(9001,ETH_HASH,ethereum_rpc=self.eth_rpc)
        # Inject a simulated valid second proof to exercise durable transaction
        # uniqueness even when application verifier had an implementation bug.
        fakeproof={"network":"ethereum-mainnet","order_id":9002}
        with patch.object(ledger,"verify_eth_transfer",return_value=fakeproof):
            with self.assertRaises(ledger.LedgerError):
                self.book.settle_verified_transfer(9002,ETH_HASH,ethereum_rpc=self.eth_rpc)
        self.assertEqual(self.book.get(9002)["status"],"awaiting")

    def test_tampered_invoice_is_not_settleable(self):
        self.book.register_invoice(self.invoice())
        with self.book.connect() as db:
            db.execute("UPDATE invoices SET sender=? WHERE order_id=?",
                       ("0x"+"e"*40,9001))
        with self.assertRaises(ValueError):
            self.book.settle_verified_transfer(9001,ETH_HASH,ethereum_rpc=self.eth_rpc)
        self.assertEqual(self.book.get(9001)["status"],"awaiting")

if __name__=="__main__":
    unittest.main()
