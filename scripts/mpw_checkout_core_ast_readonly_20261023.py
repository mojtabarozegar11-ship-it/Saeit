#!/usr/bin/env python3
"""Render a heavily redacted structural summary of the deployed checkout source.

Never transmit literal wallet addresses, file paths, email, keys, money amounts,
public URLs, passwords or raw request parameters; no app import and no SQL writes.
"""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path

APP=Path("/home/zomorod2/Saeit-staging")
ROOT=Path("/home/zomorod2/mojplaywin.com")
if APP.is_symlink() or ROOT.is_symlink() or not APP.is_dir():
    raise SystemExit("Unexpected installation")
if "APP='/home/zomorod2/Saeit-staging'" not in (ROOT/"passenger_wsgi.py").read_text("utf8","replace"):
    raise SystemExit("Unknown Passenger application")
ALLOW={"TRX","ETH","USDT","tron-mainnet","ethereum-mainnet","TRON","mainnet",
       "POST","GET","pending","awaiting","awaiting_chain","paid","failed","expired",
       "digital","digital_book","order","invoice","payment","address","amount",
       "currency","network","send","complete","confirm","receipt","wallet","product_id",
       "item_id","checkout","product","status","download","get","start","login",
       "invalid","not_found","quantity","quantity_limit"}
class Redact(ast.NodeTransformer):
    def visit_Constant(self,node):
        if type(node.value) is str and node.value not in ALLOW:
            return ast.copy_location(ast.Constant(value="<redacted-string>"),node)
        if type(node.value) is bytes:
            return ast.copy_location(ast.Constant(value=b"<bytes>"),node)
        return node

def describe(relative,selected):
    path=APP/relative
    if path.is_symlink() or not path.is_file() or path.stat().st_size>150000:
        return {"exists":False}
    raw=path.read_bytes()
    tree=ast.parse(raw,filename=relative)
    result={"exists":True,"digest_sha256":hashlib.sha256(raw).hexdigest(),
            "functions":[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))],
            "selected":{}}
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in selected:
            text=ast.unparse(Redact().visit(node))
            result["selected"][node.name]=text[:11000]
    return result

result={"read_only":True,"financial_writes":0,"core_checkout":describe(
    "core/cryptopay_checkout.py",("checkout","crypto_order","private_download","product_delivery_ready")),
    "commerce_receiver":describe("mpw_commerce/invoicing.py",("_configured_receiver","issue_invoice","create_invoice")),
    "wallet_quotes":describe("mpw_commerce/buyer_wallets.py",("fetch_server_rate",)),
    "checkout_page":describe("mpw_commerce/product_checkout_page.py",("product_checkout_page",)),
    "commerce_invoicing":describe("mpw_commerce/invoicing.py",("reserve_order_invoice",)),
    "buyer_orders":describe("mpw_commerce/buyer_orders.py",("create_order","create_buyer_order","start_checkout","_eligible")),
    "wallet_buy":describe("mpw_commerce/buyer_wallets.py",("invoice_from_verified_buyer","verify_signed_buyer_message")),
    "commerce_settlement":describe("mpw_commerce/settlement.py",("settle","reconcile","order_snapshot")),

}
print("MPW_DEPLOYED_CHECKOUT_REDACTED_AST="+json.dumps(result,sort_keys=True))
