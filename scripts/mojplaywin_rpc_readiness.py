#!/usr/bin/env python3
"""Read-only upstream RPC health check. No wallet keys, transfers or orders.

A successful probe only shows an RPC can be contacted: it does not prove
payment processing, merchant address ownership, pricing or automatic fulfilment.
"""
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError

ETH_RPC = "https://ethereum-rpc.publicnode.com"
TRON_RPC = "https://tron-rpc.publicnode.com"
TIMEOUT = 10
MAX_BYTES = 200000


def post_json(url, obj):
    request = Request(
        url,
        data=json.dumps(obj, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": "MojPlayWin-read-only-chain-check/1.0"},
        method="POST",
    )
    with urlopen(request, timeout=TIMEOUT) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("RPC response exceeded size limit")
    decoded = json.loads(body.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("RPC result was not a JSON object")
    if decoded.get("Error") or decoded.get("error"):
        raise ValueError("RPC returned an error")
    return decoded


def eth_check(post=post_json):
    chain = post(ETH_RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []})
    if chain.get("result") != "0x1":
        raise ValueError("Ethereum RPC did not confirm mainnet")
    head = post(ETH_RPC, {"jsonrpc": "2.0", "id": 2, "method": "eth_blockNumber", "params": []})
    block = head.get("result")
    if not isinstance(block, str) or not block.startswith("0x") or int(block, 16) < 1:
        raise ValueError("No confirmed ETH block height")
    return {"chain": "ethereum-mainnet", "status": "READ_ONLY_RPC_OK", "block_number": int(block, 16)}


def tron_check(post=post_json):
    # TRON GetBlock supports detail=False (header only), unlike getnowblock
    # which can return a very large list of transactions.
    data = post(TRON_RPC + "/wallet/getblock", {"detail": False})
    number = data.get("block_header", {}).get("raw_data", {}).get("number")
    if not isinstance(number, int) or number < 1 or not data.get("blockID"):
        raise ValueError("No valid TRON mainnet header; response keys=" +
                         ",".join(sorted(data.keys())[:8]))
    return {"chain": "tron-mainnet", "status": "READ_ONLY_RPC_OK",
            "block_number": number}


def main():
    failed = 0
    for label, check in [("ETH", eth_check), ("TRX", tron_check)]:
        try:
            result = check()
            print(label, result["status"], "block", result["block_number"])
        except (URLError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            print(label, "RPC_UNAVAILABLE", type(exc).__name__, str(exc)[:160])
            failed += 1
    print("NO_PAYMENTS_CREATED")
    if failed:
        return 1
    print("BOTH_MAINNET_READ_ONLY_RPCS_RESPOND")
    return 0


if __name__ == "__main__":
    sys.exit(main())
