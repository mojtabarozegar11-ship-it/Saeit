#!/usr/bin/env python3
"""MojPlayWin: actual production Django settlement+entitlement+download, fake funds.

ABSOLUTELY NO PRODUCTION DB writes: every ORM method which can mutate is
replaced by an isolated in-memory object. Uses real deployed Python business
functions + real Django route reversal + FileResponse from temporary fake PDF.
Does NOT claim a real chain transfer, a genuine receipt or paid customer.
"""
import os,sys,json,contextlib,tempfile
from pathlib import Path
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

APP=Path('/home/zomorod2/Saeit-staging')
ROOT=Path('/home/zomorod2/mojplaywin.com')
assert APP.is_dir() and not APP.is_symlink() and ROOT.is_dir() and not ROOT.is_symlink()
assert "APP='/home/zomorod2/Saeit-staging'" in (ROOT/'passenger_wsgi.py').read_text('utf8','replace')
os.chdir(APP);sys.path.insert(0,str(APP))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.utils import timezone
from django.http import Http404
from django.test import RequestFactory
from mpw_commerce import settlement as S, entitlements as E, downloads as D, checkout_views as V

price=Decimal('7.50')
now=timezone.now()
tx='a3'*32
fake_product=SimpleNamespace(pk=72,title='Simulated book - NO SALE')
file_bytes=b'%PDF-1.4\n% only a controlled simulated file, NOT a purchased book\n%%EOF\n'
records={'receipt':[],'ledger':[],'grant':[],'files_opened':0}
class Query:
 def __init__(self,rows):self.rows=list(rows)
 def filter(self,**kwargs):
  ret=[]
  for row in self.rows:
   if all(check(row,k,v) for k,v in kwargs.items()):ret.append(row)
  return Query(ret)
 def first(self):return self.rows[0] if self.rows else None
 def get(self,**kwargs):
  obj=self.filter(**kwargs).first()
  if obj is None:raise RuntimeError('Fixture row absent')
  return obj
 def exists(self):return bool(self.rows)
 def select_related(self,*fields):return self
 def select_for_update(self):return self
 def values_list(self,field,flat=False):return [getattr(x,field) for x in self.rows]
 def __getitem__(self,x):return Query(self.rows[x]) if isinstance(x,slice) else self.rows[x]
def check(row,key,value):
 if key=='order__customer_id':
  return row.order.customer_id==value
 if key=='order__status':
  return row.order.status==value
 if key=='payment_intent__isnull':
  return (row.payment_intent is None)==value
 if key=='metadata__commerce_invoice_id':
  return row.metadata['commerce_invoice_id']==value
 if key=='metadata__evidence_digest':
  return row.metadata['evidence_digest']==value
 parts=key.split('__')
 if parts[-1]=='isnull':return (getattr(row,parts[0]) is None)==value
 obj=row
 for part in parts:obj=getattr(obj,part)
 return obj==value

class FakeOrder:
 objects=None
 def __init__(self):
  self.pk=93381
  self.customer_id=77241
  self.status='pending'
  self.total=price
  self.currency='USD'
  self.items=None
 def save(self,**kwargs):pass
order=FakeOrder()
class Item:
 def __init__(self):
  self.pk=104923
  self.id=self.pk
  self.order=order
  self.product=fake_product
item=Item()
order.items=Query([item])
FakeOrder.objects=Query([order])
receivers=S.RECEIVERS.get('TRX')
if not receivers:raise RuntimeError('Active native TRX receiver is missing; do not simulate incompatible chain')
network,receiver,_=receivers
# Never print the real merchant receiving address.
invoice=SimpleNamespace(
 pk=48146,order=order,order_id=order.pk,asset='TRX',network=network,
 recipient=receiver,expected_sender='T'+'N'*33,amount_atomic=9200000,
 total_usd=price,quote_usd_per_asset=Decimal('0.80'),
 quote_observed_at=now-timedelta(seconds=40),
 issued_at=now-timedelta(minutes=2),
 expires_at=now+timedelta(minutes=7),
 sender_challenge_id='simulated-ownership-challenge',
 sender_signature_verified_at=now-timedelta(minutes=2),
 status='awaiting',save=lambda **kwargs:None)
# In production Django creates this reverse OneToOne automatically; the in-memory fixture must model it.
order.mpw_commerce_invoice=invoice
# The model names and enum constants come from the LIVE imported package,
# but all instance access and ORM writes below are redirected into memory.
InvoiceStatus=SimpleNamespace(PAID='paid',AWAITING='awaiting')
class InvoiceModel:
 objects=Query([invoice])
 Status=InvoiceStatus
 DoesNotExist=type('NoInvoice',(Exception,),{})
class OrderItemModel:
 objects=Query([item])
class Receipt:
 def __init__(self,**kwargs):self.__dict__.update(kwargs)
class ReceiptManager:
 def create(self,**kwargs):
  receipt=Receipt(**kwargs);records['receipt'].append(receipt)
  invoice.payment_receipt=receipt
  return receipt
 def filter(self,**kwargs):return Query(records['receipt']).filter(**kwargs)
class ReceiptModel:
 objects=ReceiptManager()
 DoesNotExist=type('NoReceipt',(Exception,),{})
class GrantManager:
 def create(self,**kwargs):
  grant=SimpleNamespace(**kwargs)
  records['grant'].append(grant)
  kwargs['item'].mpw_fulfillment=grant
  return grant
class GrantModel:
 objects=GrantManager()
 DoesNotExist=type('NoGrant',(Exception,),{})
 Status=SimpleNamespace(READY='ready',COMPLETE='complete',QUEUED='queued',DISPATCH='dispatch')
class LedgerManager:
 def create(self,**kwargs):
  row=SimpleNamespace(**kwargs)
  records['ledger'].append(row);return row
 def filter(self,**kwargs):return Query(records['ledger']).filter(**kwargs)
class LedgerModel:
 objects=LedgerManager()
def final_chain_proof(inv,transaction_hash):
 return {'finalized':True,'order_id':order.pk,'network':network,'tx_hash':transaction_hash,
  'sender':invoice.expected_sender,'recipient':receiver,'amount_atomic':invoice.amount_atomic,
  'backend':network+'-verified','block_timestamp':now}
def mismatched_proof(inv,transaction_hash):
 proof=final_chain_proof(inv,transaction_hash)
 proof['finalized']=False
 return proof
with contextlib.ExitStack() as st, tempfile.TemporaryDirectory(prefix='mpw-delivery-test-') as temp:
 f=Path(temp)/'simulated-item.pdf';f.write_bytes(file_bytes);f.chmod(0o600)
 patches=[
  (S,'CommerceInvoice',InvoiceModel),(S,'CommerceReceipt',ReceiptModel),
  (S,'LedgerEntry',LedgerModel),(S,'CommerceFulfillment',GrantModel),
  (S,'order_snapshot',lambda o:(price,[(item,'digital')])),
  (S,'transaction',SimpleNamespace(atomic=lambda:contextlib.nullcontext())),
  (E,'CommerceInvoice',InvoiceModel),(E,'CommerceReceipt',ReceiptModel),
  (E,'CommerceFulfillment',GrantModel),(E,'LedgerEntry',LedgerModel),
  (E,'OrderItem',OrderItemModel),(D,'OrderItem',OrderItemModel),
  (V,'CommerceInvoice',InvoiceModel),
  (V,'_ready',lambda request:True),
  (D,'_private_file',lambda obj:f),
 ]
 for mod,name,value in patches:st.enter_context(patch.object(mod,name,value))
 req=RequestFactory().get('/commerce/checkout/status/'+str(order.pk)+'/',secure=True,HTTP_HOST='mojplaywin.com')
 req.user=SimpleNamespace(pk=order.customer_id,is_authenticated=True,is_active=True)
 def check_status():
  response=V.checkout_status(req,order.pk)
  assert response.status_code==200,response.status_code
  return json.loads(response.content.decode('utf8'))
 before=check_status()
 assert before['download_paths']==[] and before['can_access_purchased_items'] is False
 assert E.can_access_purchased_digital_item(item.pk,order.customer_id) is False
 assert len(records['ledger'])==0 and len(records['receipt'])==0
 assert_fake_unpaid=None
 try:D.download_paid_item(req,item.pk)
 except Http404:assert_fake_unpaid=True
 if not assert_fake_unpaid:raise RuntimeError('Unpaid file was accessible')
 try:S.settle_order_invoice(invoice.pk,'b4'*32,trusted_chain_verifier=mismatched_proof)
 except Exception as e:
  if type(e).__name__!='SettlementRejected':raise
 else:raise RuntimeError('Forged unfinalized proof passed!')
 assert len(records['receipt'])==0 and order.status=='pending'
 # Independent negative settlement matrix: test real deployed verification
 # implementation without touching live models, ledger, orders, or customer files.
 from datetime import timedelta as _td
 bad_cases={
  'wrong_order':{'order_id':order.pk+1},
  'wrong_network':{'network':'ethereum-mainnet'},
  'wrong_sender':{'sender':'T'+'X'*33},
  'wrong_recipient':{'recipient':'T'+'Z'*33},
  'wrong_amount':{'amount_atomic':invoice.amount_atomic-1},
  'over_amount':{'amount_atomic':invoice.amount_atomic+1},
  'not_final':{'finalized':False},
  'status_truthy_string':{'finalized':'true'},
  'wrong_tx':{'tx_hash':'e5'*32},
  'wrong_backend':{'backend':'untrusted-oracle'},
  'wrong_time_before_invoice':{'block_timestamp':invoice.issued_at-_td(seconds=1)},
  'wrong_time_after_expiry':{'block_timestamp':invoice.expires_at+_td(seconds=1)},
  'absent_finalization_time':{'block_timestamp':None},
  'ambiguous_amount_type':{'amount_atomic':str(invoice.amount_atomic)},
 }
 rejected_checks=[]
 for label,change in bad_cases.items():
  def bad_verifier(inv,transaction_hash,delta=change):
   return {**final_chain_proof(inv,transaction_hash),**delta}
  try:
   S.settle_order_invoice(invoice.pk,tx,trusted_chain_verifier=bad_verifier)
  except S.SettlementRejected:
   rejected_checks.append(label)
  else:
   raise RuntimeError('Invalid proof unexpectedly settled the order: '+label)
  assert order.status=='pending' and invoice.status=='awaiting'
  assert not records['receipt'] and not records['ledger'] and not records['grant']
 assert len(rejected_checks)==len(bad_cases)
 state=S.settle_order_invoice(invoice.pk,tx,trusted_chain_verifier=final_chain_proof)
 assert state=='paid' and invoice.status=='paid' and order.status=='paid'
 assert len(records['receipt'])==1 and len(records['ledger'])==1 and len(records['grant'])==1
 assert E.can_access_purchased_digital_item(item.pk,order.customer_id) is True
 after=check_status()
 assert after['can_access_purchased_items'] is True and len(after['download_paths'])==1,after
 assert after['download_paths'][0].startswith('/')
 response=D.download_paid_item(req,item.pk)
 assert response.status_code==200
 output=b''.join(response.streaming_content)
 response.close()
 assert output==file_bytes and 'attachment' in response.get('Content-Disposition','').lower()
 replay=S.settle_order_invoice(invoice.pk,tx,trusted_chain_verifier=final_chain_proof)
 assert replay=='already_paid'
 assert len(records['receipt'])==1 and len(records['ledger'])==1 and len(records['grant'])==1
 try:S.settle_order_invoice(invoice.pk,'c6'*32,trusted_chain_verifier=final_chain_proof)
 except S.SettlementRejected:pass
 else:raise RuntimeError('Attempt to reuse paid invoice with a different tx was accepted')
 # Once a paid order loses any required financial evidence or fulfillment record,
 # the same real authorization function must deny access immediately.
 saved_receipts=list(records['receipt'])
 records['receipt'].clear()
 assert E.can_access_purchased_digital_item(item.pk,order.customer_id) is False
 records['receipt'][:]=saved_receipts
 saved_ledger=list(records['ledger'])
 records['ledger'].clear()
 assert E.can_access_purchased_digital_item(item.pk,order.customer_id) is False
 records['ledger'][:]=saved_ledger
 saved_grants=list(records['grant'])
 records['grant'].clear()
 # A OneToOne instance cache is already populated in the fixture; separately
 # revoke the object-level entitlement to exercise the missing grant path.
 prior_grant=getattr(item,'mpw_fulfillment',None)
 if prior_grant is not None:
  delattr(item,'mpw_fulfillment')
 try:
  assert E.can_access_purchased_digital_item(item.pk,order.customer_id) is False
 finally:
  if prior_grant is not None:item.mpw_fulfillment=prior_grant
 records['grant'][:]=saved_grants
 assert E.can_access_purchased_digital_item(item.pk,order.customer_id) is True
 foreign=RequestFactory().get('/commerce/checkout/status/'+str(order.pk)+'/',secure=True,HTTP_HOST='mojplaywin.com')
 foreign.user=SimpleNamespace(pk=777777,is_authenticated=True,is_active=True)
 assert V.checkout_status(foreign,order.pk).status_code==404
 try:D.download_paid_item(foreign,item.pk)
 except Http404:pass
 else:raise RuntimeError('Another buyer could retrieve paid item')
 print('MPW_SIMULATED_CRYPTO_AUTODELIVERY='+json.dumps({
  'production_models_imported':True,'no_live_database_writes':True,
  'test_environment':'isolated_in_memory_mock_ORM_with_real_Django_code',
  'asset':'TRX','network':network,
  'stage_order_created':'simulated','invalid_finality_rejected':True,
  'finalized_proof':'simulated_not_real_blockchain',
  'receipt_count':len(records['receipt']),'ledger_count':len(records['ledger']),
  'fulfillment_grants':len(records['grant']),
  'before_payment_download_denied':True,'after_payment_status_download_link':True,
  'private_fake_pdf_bytes_received':len(output),
  'other_buyer_denied':True,'same_transaction_replayed_once_only':True,
  'invalid_payment_proofs_rejected':rejected_checks,
  'different_transaction_replay_denied':True,
  'receipt_ledger_or_grant_missing_denies_download':True,
  'real_funds':0,'production_purchases_created':0,'actual_paid_delivery_proven':False},sort_keys=True))
