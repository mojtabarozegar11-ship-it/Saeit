"""Fail-closed fiat-card to native TRX merchant gateway adapter (not yet live).

Requires verified merchant on-ramp activation, payout wallet configured for native
TRX in the processor dashboard, and provider-issued secrets on server only.
"""
import hashlib
import hmac
import json
import os
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from urllib.request import Request,urlopen

API_URL="https://api.nowpayments.io/v1/invoice"
SUPPORTED_ACCOUNT_CODE="NOWPAYMENTS"
class MerchantNotReady(RuntimeError):pass
class ProviderError(RuntimeError):pass

def _approved_minimum(e):
 """Provider-confirmed, explicit minimum: prevents uneconomical micro-invoices."""
 try:
  floor=Decimal(str(e.get("MPW_FIAT_PROVIDER_MIN_USD")))
 except (InvalidOperation,TypeError,ValueError):
  return None
 if not floor.is_finite() or floor<Decimal("0.01") or floor>Decimal("1000"):
  return None
 if floor!=floor.quantize(Decimal("0.01")):
  return None
 return floor

def ready(env=None):
 e=os.environ if env is None else env
 return (e.get("MPW_FIAT_ONRAMP_APPROVED")=="1"
         and e.get("MPW_FIAT_TRX_PAYOUT_VERIFIED")=="1"
         and bool(e.get("NOWPAYMENTS_API_KEY"))
         and bool(e.get("NOWPAYMENTS_IPN_SECRET"))
         and _approved_minimum(e) is not None)

def invoice_fields(order_id,price_usd,description,callback,success,cancel):
 if not re.fullmatch(r"MPWF-[a-zA-Z0-9_-]{12,80}",str(order_id)):
  raise ValueError("Invalid unique merchant order")
 try:
  price=Decimal(str(price_usd))
 except (InvalidOperation,TypeError,ValueError) as ex:
  raise ValueError("Invalid merchant order amount") from ex
 if not price.is_finite() or price<=0 or price>Decimal("1000") or (
    price!=price.quantize(Decimal("0.01"))):
  raise ValueError("Invalid amount or unsupported sub-cent precision")
 for uri in (callback,success,cancel):
  u=urlsplit(uri)
  if u.scheme!="https" or u.hostname not in ("mojplaywin.com","www.mojplaywin.com") or u.username or u.password or u.port:
   raise ValueError("Callbacks must use the owned HTTPS merchant hostname")
 return {"price_amount":format(price,".2f"),"price_currency":"usd",
         "order_id":order_id,"order_description":str(description)[:120],
         "ipn_callback_url":callback,"success_url":success,"cancel_url":cancel}

def _official_invoice_url(value):
 if not isinstance(value,str) or len(value)>2048:raise ProviderError("Invalid invoice link")
 u=urlsplit(value)
 if u.scheme!="https" or not u.hostname or u.username or u.password or u.port:
  raise ProviderError("Untrusted invoice URL")
 hostname=u.hostname.lower()
 if hostname!="nowpayments.io" and not hostname.endswith(".nowpayments.io"):
  raise ProviderError("Unexpected invoice provider domain")
 return value

def create_invoice(order_id,price_usd,description,callback,success,cancel,*,env=None,opener=urlopen):
 e=os.environ if env is None else env
 if not ready(e):raise MerchantNotReady("Fiat-onramp TRX settlement or provider minimum is not merchant-approved")
 payload=invoice_fields(order_id,price_usd,description,callback,success,cancel)
 if Decimal(payload["price_amount"])<_approved_minimum(e):
  raise MerchantNotReady("Order is below the approved processor minimum; do not charge")
 # The processor's merchant payout configuration, NOT pay_currency in this invoice,
 # decides the TRX settlement wallet. Fiat acceptance must be activated at merchant level.
 data=json.dumps(payload,separators=(",",":")).encode("utf8")
 request=Request(API_URL,data=data,method="POST",headers={
  "Content-Type":"application/json","Accept":"application/json",
  "x-api-key":e["NOWPAYMENTS_API_KEY"],"User-Agent":"MojPlayWin-Fiat-TRX/1"})
 try:
  with opener(request,timeout=12) as response:reply=response.read(32769)
 except Exception as ex:raise ProviderError("Merchant provider did not confirm invoice creation") from ex
 if len(reply)>32768:raise ProviderError("Unbounded invoice response")
 try:
  obj=json.loads(reply.decode("utf8"))
  invoice_id=obj["id"];uri=_official_invoice_url(obj["invoice_url"])
  if not (isinstance(invoice_id,(str,int)) and str(invoice_id).isdigit()):
   raise ValueError("Missing invoice ID")
  if obj.get("order_id") not in (None,order_id):
   raise ValueError("Wrong provider order ID")
  if "price_amount" in obj and Decimal(str(obj["price_amount"]))!=Decimal(payload["price_amount"]):
   raise ValueError("Provider quoted a different price")
  if "price_currency" in obj and str(obj["price_currency"]).lower()!="usd":
   raise ValueError("Provider quoted a different currency")
 except (KeyError,ValueError,TypeError,InvalidOperation) as ex:
  raise ProviderError("Unverifiable processor invoice response") from ex
 return {"invoice_id":str(invoice_id),"invoice_url":uri,"order_id":order_id}

def _sorted_payload(value):
 if isinstance(value,dict):
  return {k:_sorted_payload(value[k]) for k in sorted(value)}
 if isinstance(value,list):
  return [_sorted_payload(v) for v in value]
 return value

def valid_webhook(raw,signature,secret):
 if not isinstance(raw,bytes) or len(raw)>32768 or not isinstance(signature,str) or not re.fullmatch(r"[a-fA-F0-9]{128}",signature):
  return False
 if not isinstance(secret,str) or not secret:return False
 try:
  message=json.loads(raw)
  if not isinstance(message,dict):return False
  canonical=json.dumps(_sorted_payload(message),separators=(",",":"),ensure_ascii=False).encode("utf8")
  expected=hmac.new(secret.encode(),canonical,hashlib.sha512).hexdigest()
  return hmac.compare_digest(expected,signature.lower())
 except (ValueError,TypeError,UnicodeDecodeError):return False

def may_fulfill(*,merchant_verified,invoice_id_matches,order_id_matches,amount_matches,
                currency_matches,settlement_native_trx_confirmed,replayed,refunded_or_partial):
 # All flags must originate from independent server-side provider state/ledger checks.
 # Never accept truthy strings/numbers (such as "false" or 1) as verified evidence.
 checks=(merchant_verified,invoice_id_matches,order_id_matches,
         amount_matches,currency_matches,settlement_native_trx_confirmed)
 return all(x is True for x in checks) and replayed is False and refunded_or_partial is False
