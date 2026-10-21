import hashlib,hmac,json,unittest
from mpw_fiat_to_trx_20261020.provider_adapter import (
 ready,invoice_fields,create_invoice,MerchantNotReady,ProviderError,valid_webhook,may_fulfill)

class FiatToTRXContractTests(unittest.TestCase):
 def test_no_kby_or_provider_key_blocks_checkout(self):
  self.assertFalse(ready({}))
  with self.assertRaises(MerchantNotReady):
   create_invoice("MPWF-AABBCC112233",7.5,"Book","https://mojplaywin.com/ipn/",
    "https://mojplaywin.com/ok/","https://mojplaywin.com/cancel/",env={})
 def test_exact_merchant_callbacks(self):
  d=invoice_fields("MPWF-AABBCC112233","7.50","Book","https://mojplaywin.com/ipn/",
   "https://mojplaywin.com/ok/","https://mojplaywin.com/cancel/")
  self.assertEqual(d["price_amount"],"7.50")
  self.assertEqual(d["price_currency"],"usd")
  self.assertNotIn("pay_currency",d)
  with self.assertRaises(ValueError):
   invoice_fields("MPWF-AABBCC112233","7.50","Book","https://evil.example/ipn/",
    "https://mojplaywin.com/ok/","https://mojplaywin.com/cancel/")
 def test_hmac_verified(self):
  msg={"order_id":"MPWF-AABBCC112233","payment_status":"finished","pay_amount":"7.50"}
  raw=json.dumps(msg).encode()
  sign=hmac.new(b"demo-secret",json.dumps(msg,sort_keys=True,separators=(",",":")).encode(),hashlib.sha512).hexdigest()
  self.assertTrue(valid_webhook(raw,sign,"demo-secret"))
  self.assertFalse(valid_webhook(raw,sign,"wrong-secret"))
 def test_unauthenticated_callback_cannot_complete(self):
  args=dict(merchant_verified=True,invoice_id_matches=True,order_id_matches=True,
            amount_matches=True,currency_matches=True,settlement_native_trx_confirmed=True,
            replayed=False,refunded_or_partial=False)
  self.assertTrue(may_fulfill(**args))
  for k in args:
   changed=dict(args)
   changed[k]=(not args[k])
   self.assertFalse(may_fulfill(**changed),k)


 def test_price_never_rounds_a_charge(self):
  for bad in ("1.005","0.001","NaN","Infinity","abc",True):
   with self.subTest(bad=bad),self.assertRaises(ValueError):
    invoice_fields("MPWF-AABBCC112233",bad,"Book","https://mojplaywin.com/ipn/",
     "https://mojplaywin.com/ok/","https://mojplaywin.com/cancel/")

 def test_merchant_minimum_required_and_micro_purchase_is_not_silently_charged(self):
  env={"MPW_FIAT_ONRAMP_APPROVED":"1","MPW_FIAT_TRX_PAYOUT_VERIFIED":"1",
       "NOWPAYMENTS_API_KEY":"test-api-key","NOWPAYMENTS_IPN_SECRET":"test-ipn-key"}
  self.assertFalse(ready(env))
  env["MPW_FIAT_PROVIDER_MIN_USD"]="3.00"  # Illustrative test value, NOT a claimed provider minimum.
  self.assertTrue(ready(env))
  def never_network(*args,**kwargs):
   raise AssertionError("Unapproved micro-invoice must never call processor")
  with self.assertRaises(MerchantNotReady):
   create_invoice("MPWF-AABBCC112233","0.03","Test PDF",
    "https://mojplaywin.com/ipn/","https://mojplaywin.com/ok/",
    "https://mojplaywin.com/cancel/",env=env,opener=never_network)
  for invalid in ("0","-1","nan","2000","0.001"):
   env["MPW_FIAT_PROVIDER_MIN_USD"]=invalid
   self.assertFalse(ready(env),invalid)

 def test_processor_echo_must_not_contradict_invoice(self):
  env={"MPW_FIAT_ONRAMP_APPROVED":"1","MPW_FIAT_TRX_PAYOUT_VERIFIED":"1",
       "NOWPAYMENTS_API_KEY":"test-api-key","NOWPAYMENTS_IPN_SECRET":"test-ipn-key",
       "MPW_FIAT_PROVIDER_MIN_USD":"3.00"}
  class Response:
   def __init__(self,payload):self.payload=payload
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self,limit):return json.dumps(self.payload).encode()
  def run(reply):
   return create_invoice("MPWF-AABBCC112233","7.50","Test PDF",
    "https://mojplaywin.com/ipn/","https://mojplaywin.com/ok/",
    "https://mojplaywin.com/cancel/",env=env,
    opener=lambda request,timeout:Response(reply))
  correct={"id":9123,"invoice_url":"https://nowpayments.io/payment/9123",
           "order_id":"MPWF-AABBCC112233","price_amount":"7.50","price_currency":"usd"}
  self.assertEqual(run(correct)["invoice_id"],"9123")
  for changed in ({"price_amount":"0.03"},{"price_currency":"eur"},
                  {"order_id":"MPWF-DIFFERENTORDER"},
                  {"invoice_url":"https://evil.example/steal"}):
   with self.subTest(changed=changed),self.assertRaises(ProviderError):
    run({**correct,**changed})

 def test_settlement_verification_flags_require_real_booleans(self):
  args=dict(merchant_verified=True,invoice_id_matches=True,order_id_matches=True,
            amount_matches=True,currency_matches=True,settlement_native_trx_confirmed=True,
            replayed=False,refunded_or_partial=False)
  self.assertTrue(may_fulfill(**args))
  for name in args:
   for ambiguous in ("false","true",1,0,None):
    with self.subTest(flag=name,value=ambiguous):
     self.assertFalse(may_fulfill(**{**args,name:ambiguous}))

if __name__=="__main__":unittest.main()
