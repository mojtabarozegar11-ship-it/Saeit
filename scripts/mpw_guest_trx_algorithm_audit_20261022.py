#!/usr/bin/env python3
"""Read-only inspect limited settlement/matcher functions. Source identifiers only, sensitive literal values redacted."""
import ast,json,os,sys,pwd,re
from pathlib import Path
P=Path('/home/zomorod2/Saeit-staging')
if pwd.getpwuid(os.getuid()).pw_name!='zomorod2' or P.is_symlink():raise RuntimeError('tenant')
targets={
'mpw_commerce/invoicing.py':['reserve_order_invoice','invoice_from_verified_buyer'],
'mpw_commerce/auto_reconcile.py':['match_unpaid_invoices','reconcile_pending_orders','discover_trx'],
'mpw_commerce/settlement.py':['_verify_evidence','settle_order_invoice','_normalized_transaction'],
'mpw_commerce/checkout_views.py':['checkout_invoice'],
'mpw_commerce/buyer_orders.py':['create_digital_order'],
}
class Sanitize(ast.NodeTransformer):
 def visit_Constant(self,node):
  if isinstance(node.value,str):
   keep={'paid','awaiting','pending','TRX','tron-mainnet','USD','expired','finalized','sender','recipient','amount_atomic','tx_hash','network','backend','order_id','block_timestamp','asset','source','verified','status','issued_at','expires_at','expected_sender','sender_challenge_id','sender_signature_verified_at','challenge_id','invoice_id','customer_id','order','quote','request_id'}
   if node.value not in keep:node.value='[TEXT]'
  return self.generic_visit(node)
for rel,names in targets.items():
 f=P/rel
 if not f.is_file():continue
 tree=ast.parse(f.read_text('utf8','replace'))
 for x in tree.body:
  if not isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) or x.name not in names:continue
  safe=Sanitize().visit(x)
  print('GUEST_ALGORITHM='+json.dumps({'file':rel,'function':x.name,'source':ast.unparse(safe)[:14000]}))
print('GUEST_ALGORITHM_READONLY=PASS')
