#!/usr/bin/env python3
"""No-funds mainnet-shape mock of ETH/TRX gateway CLI settlement.

All RPC responses are served by a disposable loopback HTTP server on the CI
runner, never the public chain. Uses only a private temp SQLite DB. Exercises
the EXACT source PHP verifier, with endpoint and DB paths changed in a
temporary copy. No wallets, live URLs or merchant DB touched.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time

SOURCE = Path(__file__).resolve().parents[1] / "isolated_crypto_gateway"
ETH_ADDRESS = "0x89149b01f59115B86553561F12438D2ADF517E75"
TRX_RECIPIENT_HEX = "414FD76FC6FB6370DCC86170E9695610EBF559DDAD"
ETH_QUOTE = 10000000000000000 + 47
TRX_QUOTE = 10000000 + 49
BLOCK_HASH = "0x" + "b" * 64
ETH_TX = "0x" + "a" * 64
TRX_TX = "c" * 64
WRONG_TRX_TX = "d" * 64
WRONG_ETH_TX = "0x" + "e" * 64


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not self.path.startswith(("/eth", "/walletsolidity/")):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length < 8192:
                self.send_error(400)
                return
            arg = json.loads(self.rfile.read(length))
            if self.path == "/eth":
                method = arg["method"]
                txid = arg.get("params", [None])[0] if arg.get("params") else None
                amount = ETH_QUOTE + (1 if txid == WRONG_ETH_TX else 0)
                fixtures = {
                    "eth_chainId": "0x1",
                    "eth_getTransactionByHash": {
                        "hash": txid, "to": ETH_ADDRESS, "value": hex(amount),
                        "blockNumber": "0x64", "blockHash": BLOCK_HASH,
                    },
                    "eth_getTransactionReceipt": {
                        "transactionHash": txid, "status": "0x1",
                        "blockNumber": "0x64", "blockHash": BLOCK_HASH,
                    },
                    "eth_getBlockByNumber": {
                        "number": "0x64", "hash": BLOCK_HASH,
                        "timestamp": hex(int(time.time())),
                    },
                    "eth_blockNumber": "0x7f",
                }
                out = {"jsonrpc": "2.0", "id": 1, "result": fixtures[method]}
            else:
                method = self.path.split("/")[-1]
                token = arg.get("value", "")
                destination = (
                    TRX_RECIPIENT_HEX if token == TRX_TX else ("41" + "0" * 40)
                )
                fixtures = {
                    "gettransactionbyid": {
                        "txID": token,
                        "raw_data": {"contract": [{
                            "type": "TransferContract",
                            "parameter": {"value": {
                                "to_address": destination, "amount": TRX_QUOTE,
                            }},
                        }]},
                        "ret": [{"contractRet": "SUCCESS"}],
                    },
                    "gettransactioninfobyid": {
                        "id": token, "blockNumber": 100,
                        "blockTimeStamp": int(time.time()) * 1000,
                        "receipt": {"net_fee": 100},
                    },
                    "getnowblock": {"block_header": {"raw_data": {"number": 130}}},
                }
                out = fixtures[method]
            blob = json.dumps(out).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)
        except (ValueError, KeyError, TypeError):
            self.send_error(400)

    def log_message(self, *_args):
        return


def main():
    if not shutil.which("php"):
        raise RuntimeError("PHP CLI is required for this gateway test")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="mojplaywin-chain-mock-") as folder:
            root = Path(folder)
            private = root / "private"
            port = server.server_address[1]
            php_src = (SOURCE / "index.php").read_text()
            php_src = php_src.replace(
                "const ETH_RPC='https://ethereum-rpc.publicnode.com';",
                f"const ETH_RPC='http://127.0.0.1:{port}/eth';"
            ).replace(
                "const TRX_RPC='https://api.trongrid.io/walletsolidity/';",
                f"const TRX_RPC='http://127.0.0.1:{port}/walletsolidity/';"
            ).replace(
                "const DATA='/home/zomorod2/.mojplaywin-crypto-payments-v1';",
                f"const DATA='{private}';"
            )
            bootstrap = (SOURCE / "bootstrap.php").read_text()
            bootstrap = bootstrap.replace(
                "$root='/home/zomorod2/.mojplaywin-crypto-payments-v1';",
                f"$root='{private}';"
            )
            assert php_src != (SOURCE / "index.php").read_text()
            assert f"const DATA='{private}';" in php_src
            assert f"$root='{private}';" in bootstrap
            (root / "index.php").write_text(php_src)
            (root / "bootstrap.php").write_text(bootstrap)
            for name in ("index.php", "bootstrap.php"):
                subprocess.run(["php", "-l", str(root / name)], check=True, capture_output=True)
            subprocess.run(["php", str(root / "bootstrap.php"), "init"], check=True, capture_output=True)
            (private / "enabled.flag").touch()
            now = int(time.time())
            db = sqlite3.connect(private / "payments.sqlite3")
            entries = [
                ("a" * 48, "ETH", ETH_QUOTE, ETH_TX),
                ("b" * 48, "TRX", TRX_QUOTE, TRX_TX),
                ("c" * 48, "TRX", TRX_QUOTE + 1, WRONG_TRX_TX),
                ("d" * 48, "ETH", ETH_QUOTE + 2, WRONG_ETH_TX),
            ]
            for token, asset, quote, txid in entries:
                db.execute(
                    "INSERT INTO invoices (token,asset,base,quote,merchant,reference,created_at,expires_at,status,tx_hash) "
                    "VALUES (?,?,?,?,?,?,?,?,'confirming',?)",
                    (token, asset, quote - 47, quote,
                     ETH_ADDRESS if asset == "ETH" else "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73",
                     "OFFLINE TEST, NO MONEY", now - 30, now + 1800, txid),
                )
            db.commit()
            first = subprocess.run(
                ["php", str(root / "index.php"), "reconcile"],
                capture_output=True, text=True, timeout=35, check=True,
            )
            assert "MOJPLAYWIN_AUTORECONCILE_PAID=2" in first.stdout, first.stdout
            assert "MOJPLAYWIN_AUTORECONCILE_ERRORS=2" in first.stdout, first.stdout
            for token, _, _, _ in entries:
                status, paid_at = db.execute(
                    "SELECT status,paid_at FROM invoices WHERE token=?", (token,)
                ).fetchone()
                expected = "paid" if token[0] in "ab" else "confirming"
                assert status == expected, (token, status, expected)
                assert (paid_at is not None) == (expected == "paid")
            second = subprocess.run(
                ["php", str(root / "index.php"), "reconcile"],
                capture_output=True, text=True, timeout=35, check=True,
            )
            assert "MOJPLAYWIN_AUTORECONCILE_PAID=0" in second.stdout
            assert "MOJPLAYWIN_AUTORECONCILE_ERRORS=2" in second.stdout
            print("OFFLINE_ETH_FULL_CONFIRMED_AUTO_SETTLEMENT=true")
            print("OFFLINE_TRX_NATIVE_OPTIONAL_RECEIPT_CONFIRMED_AUTO_SETTLEMENT=true")
            print("WRONG_RECIPIENT_OR_AMOUNT_WAS_NEVER_SETTLED=true")
            print("REPEAT_AUTO_RECONCILE_PAID_AGAIN=0")
            print("ACTUAL_FUNDS_TRANSFERRED=false")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
