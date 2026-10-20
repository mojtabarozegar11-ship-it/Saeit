"""Fail-closed native TRON solidity proof; no screenshots or self-reported payments."""
import re,time,sqlite3
from scripts.mojplaywin_native_chain_verify import LockedQuote,verify_trx_transfer,TRX_RECEIVER
from scripts.mojplaywin_native_rpc_clients import tron_solidity_rpc
from .guest_database import connect
from .guest_pricing import receive_wallet

def confirm(order,transaction_id):
 tx=transaction_id.lower()
 if not re.fullmatch("[a-f0-9]{64}",tx):raise ValueError("Invalid TRX transaction hash")
 if order["status"]!="pending":raise ValueError("Invoice already finalized")
 if receive_wallet()!=TRX_RECEIVER or order["receiver"]!=TRX_RECEIVER:
  raise RuntimeError("Merchant receiver configuration mismatch")
 q=LockedQuote(order_id=order["id"],network="tron-mainnet",
  smallest_units=order["amount_sun"],expected_sender=order["sender"],
  created_at_ms=order["issued_ms"],expires_at_ms=order["expires_ms"],
  quote_currency="USD",quote_amount=order["usd"])
 proof=verify_trx_transfer(tx,q,tron_solidity_rpc)
 if proof.get("transaction_hash")!=tx or proof.get("finality")!="tron-solidity":
  raise ValueError("TRX finality evidence missing")
 db=connect()
 try:
  db.execute("BEGIN IMMEDIATE")
  updated=db.execute("UPDATE guest_orders SET status='paid',txid=? WHERE id=? AND status='pending' AND claim_sha=?",
   (tx,order["id"],order["claim_sha"]))
  if updated.rowcount!=1:raise RuntimeError("Concurrent invoice change")
  db.commit()
 except sqlite3.IntegrityError as exc:
  raise ValueError("Transaction already attributed to another order") from exc
 finally:db.close()
 return True
