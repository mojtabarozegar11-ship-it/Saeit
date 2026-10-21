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
MIN_URL="https://api.nowpayments.io/v1/min-amount?currency_from=trx&currency_to=trx&fiat_equivalent=usd"
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

def live_trx_minimum_usd(env, *, opener=urlopen):
 """Fetch fresh provider minimum in USD equivalent for native TRX -> TRX.

 Cryptocurrency minimums do not prove that fiat/card on-ramp is authorized.
 Reject stale/malformed responses; NEVER guess or substitute a hardcoded quote.
 """
 if not env.get("NOWPAYMENTS_API_KEY"):
  raise MerchantNotReady("Merchant API key is missing")
 request=Request(MIN_URL,method="GET",headers={
  "Accept":"application/json","x-api-key":env["NOWPAYMENTS_API_KEY"],
  "User-Agent":"MojPlayWin-TRX-Minimum/1"})
 try:
  with opener(request,timeout=12) as response:raw=response.read(4097)
 except Exception as exc:
  raise MerchantNotReady("The processor minimum could not be independently verified") from exc
 if len(raw)>4096:raise MerchantNotReady("Oversized processor minimum response")
 try:
  result=json.loads(raw.decode("utf8"))
  if not isinstance(result,dict):raise ValueError("Invalid minimum response object")
  for name,expected in (("currency_from","trx"),("currency_to","trx")):
   if name in result and str(result[name]).lower()!=expected:
    raise ValueError("Wrong payment network/currency in minimum response")
  amount=result["fiat_equivalent"]
  if type(amount) not in (str,int,float):raise ValueError("Invalid fiat minimum type")
  minimum=Decimal(str(amount))
  if not minimum.is_finite() or minimum<=0 or minimum>Decimal("1000"):
   raise ValueError("Invalid processor minimum amount")
 except (KeyError,ValueError,TypeError,UnicodeDecodeError,InvalidOperation) as exc:
  raise MerchantNotReady("Unverifiable processor minimum fiat equivalent") from exc
 return minimum


def create_invoice(order_id,price_usd,description,callback,success,cancel,*,env=None,opener=urlopen,min_opener=urlopen):
 e=os.environ if env is None else env
 if not ready(e):raise MerchantNotReady("Fiat-onramp TRX settlement or provider minimum is not merchant-approved")
 payload=invoice_fields(order_id,price_usd,description,callback,success,cancel)
 price=Decimal(payload["price_amount"])
 if price<_approved_minimum(e):
  raise MerchantNotReady("Order is below the merchant-approved minimum; do not charge")
 # Never use a static merchant threshold instead of the provider's live minimum.
 # This validates the native TRX crypto rail only; independent fiat/card approval
 # and confirmed merchant TRX settlement remain mandatory.
 if price<live_trx_minimum_usd(e,opener=min_opener):
  raise MerchantNotReady("Order is below the live TRX network payment minimum")
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


# Read-only, dual-source proof. Even a valid API proof never authorizes fulfillment
# without checking the merchant's confirmed, native-TRX payout independently.
def verify_processor_payment(*, payment_id, invoice_id, order_id, price_usd,
                             signed_ipn_raw, signed_ipn_signature, env=None,
                             opener=urlopen):
 e=os.environ if env is None else env
 if not ready(e):
  raise MerchantNotReady("Processor and TRX merchant settlement are not approved")
 if not re.fullmatch(r"[0-9]{1,22}",str(payment_id)) or type(payment_id) is bool:
  raise ValueError("Invalid processor payment identifier")
 if not re.fullmatch(r"[0-9]{1,22}",str(invoice_id)) or type(invoice_id) is bool:
  raise ValueError("Invalid processor invoice identifier")
 if not re.fullmatch(r"MPWF-[a-zA-Z0-9_-]{12,80}",str(order_id)):
  raise ValueError("Invalid unique merchant order")
 try:
  expected_price=Decimal(str(price_usd))
 except (ValueError,TypeError,InvalidOperation) as exc:
  raise ValueError("Invalid price") from exc
 if (not expected_price.is_finite() or expected_price<=0
     or expected_price!=expected_price.quantize(Decimal("0.01"))):
  raise ValueError("Invalid exact price")
 if not valid_webhook(signed_ipn_raw,signed_ipn_signature,e["NOWPAYMENTS_IPN_SECRET"]):
  raise ProviderError("Untrusted IPN notification")
 try:
  ipn=json.loads(signed_ipn_raw.decode("utf8"))
 except (ValueError,UnicodeDecodeError) as exc:
  raise ProviderError("Unreadable authenticated IPN") from exc
 request=Request("https://api.nowpayments.io/v1/payment/"+str(payment_id),
  method="GET",headers={"Accept":"application/json","x-api-key":e["NOWPAYMENTS_API_KEY"],
                         "User-Agent":"MojPlayWin-Reconciliation/1"})
 try:
  with opener(request,timeout=12) as reply:raw=reply.read(32769)
 except Exception as exc:
  raise ProviderError("Independent processor verification unavailable") from exc
 if len(raw)>32768:raise ProviderError("Unbounded provider verification")
 try: current=json.loads(raw.decode("utf8"))
 except (ValueError,UnicodeDecodeError) as exc:
  raise ProviderError("Malformed independent provider status") from exc
 def same_status(proof):
  if not isinstance(proof,dict):return False
  if (str(proof.get("payment_id"))!=str(payment_id) or
      str(proof.get("invoice_id"))!=str(invoice_id) or
      proof.get("order_id")!=order_id or
      proof.get("payment_status")!="finished" or
      str(proof.get("price_currency","")).lower()!="usd" or
      str(proof.get("outcome_currency","")).lower()!="trx"):
   return False
  try:
   amount=Decimal(str(proof["price_amount"]))
   received=Decimal(str(proof["outcome_amount"]))
   paid=Decimal(str(proof["actually_paid"]))
   pay_amount=Decimal(str(proof["pay_amount"]))
  except (KeyError,TypeError,ValueError,InvalidOperation):
   return False
  return (all(v.is_finite() for v in (amount,received,paid,pay_amount))
          and amount==expected_price and received>0 and pay_amount>0
          and paid>=pay_amount)
 if not same_status(ipn) or not same_status(current):
  raise ProviderError("Signed IPN does not agree with final independent provider payment")
 for field in ("pay_currency","pay_amount","outcome_currency","outcome_amount","actually_paid"):
  if str(ipn.get(field)).lower()!=str(current.get(field)).lower():
   raise ProviderError("Signed payment and provider reconciliation differ")
 # This is intentionally NOT a paid-delivery authorization, not an on-chain or
 # merchant payout receipt and not a fiat-onramp KYC proof.
 return {"payment_id":str(payment_id),"invoice_id":str(invoice_id),
         "order_id":order_id,"provider_finished_verified":True,
         "native_trx_merchant_settlement_verified":False,
         "safe_to_fulfill":False}
