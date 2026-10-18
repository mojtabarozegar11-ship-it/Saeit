"""Mock trusted nodes: ensure no RPC field mismatch can mark a transfer paid."""
from unittest.mock import patch
import pytest
from core.mojplaywin_chain_verify import verify_eth, verify_trx, VerificationError, _tron_address_hex


def test_eth_chain_recipient_value_success_and_confirmations():
    txid = "0x" + "a" * 64
    wallet = "0x" + "b" * 40
    block_hash = "0x" + "c" * 64
    values = {
        "eth_chainId": "0x1",
        "eth_getTransactionByHash": {"hash": txid, "to": wallet, "value": "0x64", "blockNumber": "0x64", "blockHash": block_hash},
        "eth_getTransactionReceipt": {"transactionHash": txid, "status": "0x1", "blockNumber": "0x64", "blockHash": block_hash},
        "eth_getBlockByNumber": {"number": "0x64", "hash": block_hash, "timestamp": "0x6553f100"},
        "eth_blockNumber": "0x70",
    }
    with patch("core.mojplaywin_chain_verify._rpc", side_effect=lambda url,method,params: values[method]):
        proof = verify_eth(txid, wallet, 100, "https://rpc.example.org")
        assert proof.confirmations == 13
        assert proof.timestamp_ms == 0x6553f100 * 1000
        values["eth_chainId"] = "0x5"
        with pytest.raises(VerificationError, match="Wrong Ethereum"):
            verify_eth(txid, wallet, 100, "https://rpc.example.org")
        values["eth_chainId"] = "0x1"
        values["eth_getTransactionByHash"]["to"] = "0x" + "c" * 40
        with pytest.raises(VerificationError, match="recipient"):
            verify_eth(txid, wallet, 100, "https://rpc.example.org")


def test_tron_address_checksum_rejects_bad_destination():
    with pytest.raises(VerificationError):
        _tron_address_hex("not-a-mainnet-address")
    with pytest.raises(VerificationError):
        verify_trx("a" * 64, "not-valid", 100)


def test_eth_rejects_inconsistent_canonical_block_hash():
    txid = "0x" + "e" * 64
    wallet = "0x" + "b" * 40
    a, b = "0x" + "c" * 64, "0x" + "d" * 64
    data = {
        "eth_chainId": "0x1",
        "eth_getTransactionByHash": {"hash": txid, "to": wallet, "value": "0x64", "blockNumber": "0x64", "blockHash": a},
        "eth_getTransactionReceipt": {"transactionHash": txid, "status": "0x1", "blockNumber": "0x64", "blockHash": b},
        "eth_getBlockByNumber": {"number": "0x64", "hash": a, "timestamp": "0x6553f100"},
        "eth_blockNumber": "0x70",
    }
    with patch("core.mojplaywin_chain_verify._rpc", side_effect=lambda url, method, params: data[method]):
        with pytest.raises(VerificationError, match="block hash mismatch"):
            verify_eth(txid, wallet, 100, "https://rpc.example.org")
