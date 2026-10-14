"""Read-only mocked discovery tests. No real wallets, chain writes or payment state."""
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mojplaywin_direct_wallet_discovery as d
from mojplaywin_native_chain_verify import tron_address_to_hex

NOW = 1700000100000
ETH_TX = "0x" + "a"*64
TRX_TX = "c"*64
SENDER = "0x" + "d"*40


class DiscoverTests(unittest.TestCase):
    def eth_item(self, *, address=None, value="1234567", timestamp="2023-11-14T22:14:20Z", txid=ETH_TX):
        return {"hash":txid,"from":{"hash":SENDER},
                "to":{"hash":address or d.ETH_WALLET},
                "value":value,"timestamp":timestamp}

    def trx_item(self, *, address=None, value=999, txid=TRX_TX,
                 sender=None, kind="TransferContract"):
        return {"txID":txid,"raw_data":{
            "timestamp":NOW-20000,"contract":[{"type":kind,"parameter":{"value":{
            "owner_address":sender or tron_address_to_hex(d.TRX_WALLET),
            "to_address":address or tron_address_to_hex(d.TRX_WALLET),
            "amount":value}}}]}}

    def test_eth_positive_inbound_is_candidate_only(self):
        rows=d.discover_eth(now_ms=NOW,load=lambda url:{"items":[self.eth_item()],"next_page_params":None})
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].tx_hash,ETH_TX)
        self.assertEqual(rows[0].amount_atomic,"1234567")

    def test_eth_wrong_destination_is_ignored(self):
        rows=d.discover_eth(now_ms=NOW,load=lambda url:{"items":[self.eth_item(address=SENDER)],"next_page_params":None})
        self.assertEqual(rows,[])

    def test_eth_wrong_timestamp_outside_window(self):
        rows=d.discover_eth(now_ms=NOW,load=lambda url:{"items":[
            self.eth_item(timestamp="2023-11-14T21:10:20Z")],"next_page_params":None})
        self.assertEqual(rows,[])

    def test_eth_rejects_negative_indexer_amount(self):
        with self.assertRaises(d.IndexerUnavailable):
            d.discover_eth(now_ms=NOW,load=lambda url:{"items":[self.eth_item(value="-1")]})

    def test_eth_pagination_uses_only_numeric_params(self):
        seen=[]
        def loader(url):
            seen.append(url)
            if len(seen)==1:
                return {"items":[self.eth_item()],"next_page_params":{"block_number":10,"index":4,"items_count":50}}
            return {"items":[],"next_page_params":None}
        rows=d.discover_eth(now_ms=NOW,load=loader)
        self.assertEqual(len(rows),1)
        self.assertEqual(parse_qs(urlparse(seen[-1]).query)["block_number"],["10"])

    def test_eth_pagination_host_cannot_be_redirected(self):
        with self.assertRaises(d.IndexerUnavailable):
            d.discover_eth(now_ms=NOW,load=lambda url:{"items":[],"next_page_params":{"redirect":"https://bad.example"}})

    def test_eth_repeating_page_fails_closed(self):
        with self.assertRaises(d.IncompleteDiscovery):
            d.discover_eth(now_ms=NOW,load=lambda url:{"items":[],"next_page_params":{"index":2}})

    def test_eth_page_limit_fails_closed(self):
        with self.assertRaises(d.IncompleteDiscovery):
            d.discover_eth(now_ms=NOW,max_pages=1,load=lambda url:{
                "items":[self.eth_item()],"next_page_params":{"index":2}
            })

    def test_trx_positive_native_payment_discovered(self):
        rows=d.discover_trx(now_ms=NOW,load=lambda url:{"data":[self.trx_item()],"meta":{}})
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].tx_hash,TRX_TX)
        self.assertEqual(rows[0].amount_atomic,"999")

    def test_trx_token_contract_not_native_coin(self):
        rows=d.discover_trx(now_ms=NOW,load=lambda url:{"data":[self.trx_item(kind="TriggerSmartContract")],"meta":{}})
        self.assertEqual(rows,[])

    def test_trx_wrong_receiver_ignored(self):
        other="41"+"a"*40
        rows=d.discover_trx(now_ms=NOW,load=lambda url:{"data":[self.trx_item(address=other)],"meta":{}})
        self.assertEqual(rows,[])

    def test_trx_pagination_rejects_url_in_fingerprint(self):
        with self.assertRaises(d.IndexerUnavailable):
            d.discover_trx(now_ms=NOW,load=lambda url:{
                "data":[],"meta":{"fingerprint":"https://bad.example/"}
            })

    def test_trx_page_limit_fails_closed(self):
        with self.assertRaises(d.IncompleteDiscovery):
            d.discover_trx(now_ms=NOW,max_pages=1,load=lambda url:{
                "data":[self.trx_item()],"meta":{"fingerprint":"abc123"}
            })

    def test_trx_future_timestamp_is_blocked(self):
        bogus=self.trx_item()
        bogus["raw_data"]["timestamp"]=NOW+120_000
        with self.assertRaises(d.IndexerUnavailable):
            d.discover_trx(now_ms=NOW,load=lambda url:{"data":[bogus],"meta":{}})

    def test_transaction_candidate_matches_exact_invoice_fields_only(self):
        invoice=SimpleNamespace(pk=72,network="ethereum-mainnet",
                verified_sender_address=SENDER,merchant_address=d.ETH_WALLET,
                amount_atomic="1234567")
        candidate=d.Candidate("ethereum-mainnet",ETH_TX,SENDER.lower(),d.ETH_WALLET.lower(),
                              "1234567",NOW-20000)
        matches=d.match_unpaid_invoices([invoice],[candidate,candidate])
        self.assertEqual(matches,[(72,ETH_TX)])
        self.assertEqual(d.match_unpaid_invoices([invoice],[
            d.Candidate("ethereum-mainnet",ETH_TX,SENDER.lower(),d.ETH_WALLET.lower(),
                         "1234568",NOW-20000)
        ]),[])

    def test_ambiguous_invoices_fail_closed(self):
        a=SimpleNamespace(pk=3,network="ethereum-mainnet",verified_sender_address=SENDER,
                          merchant_address=d.ETH_WALLET,amount_atomic="999")
        b=SimpleNamespace(pk=4,network="ethereum-mainnet",verified_sender_address=SENDER,
                          merchant_address=d.ETH_WALLET,amount_atomic="999")
        with self.assertRaises(d.IncompleteDiscovery):
            d.match_unpaid_invoices([a,b],[])

    def test_invalid_request_bound_fails(self):
        with self.assertRaises(d.IndexerUnavailable):
            d.discover_eth(now_ms=NOW, max_pages=0,load=lambda x:{})

if __name__=="__main__":
    unittest.main()
