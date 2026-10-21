import hashlib,hmac,json,unittest
from mpw_fiat_to_trx_20261020.provider_adapter import (
 ready,invoice_fields,create_invoice,live_trx_minimum_usd,verify_processor_payment,MerchantNotReady,ProviderError,valid_webhook,may_fulfill)

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
    opener=lambda request,timeout:Response(reply),
    min_opener=lambda request,timeout:Response({"min_amount":"10","fiat_equivalent":"2.70","currency_from":"trx","currency_to":"trx"}))
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


 def test_live_trx_minimum_is_from_official_endpoint(self):
  env={"NOWPAYMENTS_API_KEY":"test-key"}
  class Response:
   def __init__(self,data):self.data=data
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self,size):return json.dumps(self.data).encode()
  def expected(req,timeout):
   self.assertEqual(req.get_method(),"GET")
   self.assertEqual(req.full_url,
    "https://api.nowpayments.io/v1/min-amount?currency_from=trx&currency_to=trx&fiat_equivalent=usd")
   return Response({"min_amount":"12.3","fiat_equivalent":"3.15",
                    "currency_from":"trx","currency_to":"trx"})
  self.assertEqual(str(live_trx_minimum_usd(env,opener=expected)),"3.15")

 def test_missing_or_invalid_live_minimum_blocks_before_invoice(self):
  env={"MPW_FIAT_ONRAMP_APPROVED":"1","MPW_FIAT_TRX_PAYOUT_VERIFIED":"1",
       "NOWPAYMENTS_API_KEY":"test-key","NOWPAYMENTS_IPN_SECRET":"test-ipn",
       "MPW_FIAT_PROVIDER_MIN_USD":"0.01"}
  class Response:
   def __init__(self,data):self.data=data
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self,size):return json.dumps(self.data).encode()
  def invoice_must_not_be_created(req,timeout):
   raise AssertionError("Invoice API must not be called")
  samples=(
    {"min_amount":"15.0","fiat_equivalent":"8.00"},
    {"min_amount":"7","fiat_equivalent":"NaN"},
    {"fiat_equivalent":"-2"},
    {"fiat_equivalent":"1.00","currency_to":"usdttrc20"},
    {"fiat_equivalent":True},
    [],
  )
  for response in samples:
   with self.subTest(response=response),self.assertRaises(MerchantNotReady):
    create_invoice("MPWF-AABBCC112233","7.50","Book",
      "https://mojplaywin.com/ipn/","https://mojplaywin.com/ok/",
      "https://mojplaywin.com/cancel/",env=env,
      opener=invoice_must_not_be_created,
      min_opener=lambda req,timeout:Response(response))
  with self.assertRaises(MerchantNotReady):
   create_invoice("MPWF-AABBCC112233","7.50","Book",
      "https://mojplaywin.com/ipn/","https://mojplaywin.com/ok/",
      "https://mojplaywin.com/cancel/",env=env,
      opener=invoice_must_not_be_created,
      min_opener=lambda req,timeout:(_ for _ in ()).throw(TimeoutError()))

 def test_provider_minimum_must_not_be_guessed_from_static_merchant_floor(self):
  env={"MPW_FIAT_ONRAMP_APPROVED":"1","MPW_FIAT_TRX_PAYOUT_VERIFIED":"1",
       "NOWPAYMENTS_API_KEY":"test-key","NOWPAYMENTS_IPN_SECRET":"test-ipn",
       "MPW_FIAT_PROVIDER_MIN_USD":"0.01"}
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self,size):return b'{"min_amount":"100","fiat_equivalent":"12.00"}'
  with self.assertRaises(MerchantNotReady):
   create_invoice("MPWF-AABBCC112233","0.03","Test PDF",
      "https://mojplaywin.com/ipn/","https://mojplaywin.com/ok/",
      "https://mojplaywin.com/cancel/",env=env,
      opener=lambda req,timeout:(_ for _ in ()).throw(AssertionError("unacceptable micro invoice")),
      min_opener=lambda req,timeout:Response())


 def test_authenticated_webhook_requires_independent_provider_match(self):
  env={"MPW_FIAT_ONRAMP_APPROVED":"1","MPW_FIAT_TRX_PAYOUT_VERIFIED":"1",
       "NOWPAYMENTS_API_KEY":"mock-api-key","NOWPAYMENTS_IPN_SECRET":"mock-secret",
       "MPW_FIAT_PROVIDER_MIN_USD":"2.00"}
  payload={"payment_id":123456,"invoice_id":901234,"order_id":"MPWF-AABBCC112233",
           "payment_status":"finished","price_amount":7.5,"price_currency":"usd",
           "pay_currency":"trx","pay_amount":22,"actually_paid":22,
           "outcome_currency":"trx","outcome_amount":21.7}
  raw=json.dumps(payload).encode()
  sig=hmac.new(env["NOWPAYMENTS_IPN_SECRET"].encode(),
     json.dumps(payload,sort_keys=True,separators=(",",":")).encode(),hashlib.sha512).hexdigest()
  class Response:
   def __init__(self,info):self.info=info
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self,amount):return json.dumps(self.info).encode()
  def test(reply,**overrides):
   arguments={"payment_id":123456,"invoice_id":901234,"order_id":"MPWF-AABBCC112233",
              "price_usd":"7.50","signed_ipn_raw":raw,"signed_ipn_signature":sig,
              "env":env,"opener":lambda req,timeout:Response(reply)}
   arguments.update(overrides)
   return verify_processor_payment(**arguments)
  result=test(payload)
  self.assertTrue(result["provider_finished_verified"])
  self.assertFalse(result["native_trx_merchant_settlement_verified"])
  self.assertFalse(result["safe_to_fulfill"])
  for different in (
    {"payment_status":"confirming"},{"outcome_currency":"usdttrc20"},
    {"price_amount":8.00},{"order_id":"MPWF-UNRELATED12345"},
    {"payment_id":4321},{"invoice_id":901235},
    {"actually_paid":15},{"outcome_amount":0},
    {"pay_currency":"usdttrc20"},
  ):
   with self.subTest(change=different),self.assertRaises(ProviderError):
    test({**payload,**different})
  with self.assertRaises(ProviderError):
   test(payload,signed_ipn_signature="0"*128)
  with self.assertRaises(ProviderError):
   test(payload,opener=lambda req,timeout:(_ for _ in ()).throw(TimeoutError()))
  for invalid in ("1/../../2","no-id",-1,True):
   with self.subTest(payment_id=invalid),self.assertRaises(ValueError):
    test(payload,payment_id=invalid)

 def test_final_state_never_authorizes_paid_fulfillment_alone(self):
  env={"MPW_FIAT_ONRAMP_APPROVED":"1","MPW_FIAT_TRX_PAYOUT_VERIFIED":"1",
       "NOWPAYMENTS_API_KEY":"mock-api-key","NOWPAYMENTS_IPN_SECRET":"mock-secret",
       "MPW_FIAT_PROVIDER_MIN_USD":"0.10"}
  response={"payment_id":987,"invoice_id":456,"order_id":"MPWF-MYRECEIPT12345",
            "payment_status":"finished","price_amount":"4.00","price_currency":"usd",
            "pay_currency":"trx","pay_amount":"20.50","actually_paid":"20.50",
            "outcome_amount":"20.30","outcome_currency":"trx"}
  class R:
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self,size):return json.dumps(response).encode()
  raw=json.dumps(response).encode()
  signature=hmac.new(env["NOWPAYMENTS_IPN_SECRET"].encode(),
    json.dumps(response,sort_keys=True,separators=(",",":")).encode(),hashlib.sha512).hexdigest()
  receipt=verify_processor_payment(payment_id=987,invoice_id=456,
    order_id="MPWF-MYRECEIPT12345",price_usd="4.00",signed_ipn_raw=raw,
    signed_ipn_signature=signature,env=env,opener=lambda req,timeout:R())
  self.assertFalse(receipt["safe_to_fulfill"])
  self.assertFalse(receipt["native_trx_merchant_settlement_verified"])


 def test_minimum_rejects_invalid_native_trx_amount_even_with_valid_fiat(self):
  env={"NOWPAYMENTS_API_KEY":"mock-api"}
  class Response:
   def __init__(self,obj):self.obj=obj
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self,limit):return json.dumps(self.obj).encode()
  for bad in ("0","-1","NaN","Infinity","no value",True,None):
   with self.subTest(minimum=bad),self.assertRaises(MerchantNotReady):
    live_trx_minimum_usd(env,opener=lambda req,timeout:Response({
      "min_amount":bad,"fiat_equivalent":"3.00","currency_from":"trx","currency_to":"trx"}))

 def test_signed_webhook_rejects_duplicate_and_nonfinite_json(self):
  key="test-signed-secret"
  for raw in (b'{"payment_id":1,"payment_id":2,"order_id":"MPW"}',
              b'{"payment_id":1,"nested":{"order_id":"good","order_id":"wrong"}}',
              b'{"payment_status":NaN}',b'{"payment_status":Infinity}',
              b'[{"payment_status":"finished"}]'):
   with self.subTest(json=raw.decode()):
    sig=hmac.new(key.encode(),
       json.dumps(json.loads(raw),sort_keys=True,separators=(",",":")).encode(),
       hashlib.sha512).hexdigest()
    self.assertFalse(valid_webhook(raw,sig,key))

 def test_independent_payment_status_rejects_duplicate_keys(self):
  env={"MPW_FIAT_ONRAMP_APPROVED":"1","MPW_FIAT_TRX_PAYOUT_VERIFIED":"1",
       "NOWPAYMENTS_API_KEY":"mock-key","NOWPAYMENTS_IPN_SECRET":"test-key",
       "MPW_FIAT_PROVIDER_MIN_USD":"1.00"}
  valid={"payment_id":987,"invoice_id":654,"order_id":"MPWF-SECURE1234567",
         "price_amount": "4.00","price_currency":"usd","payment_status":"finished",
         "pay_currency":"trx","pay_amount":20,"actually_paid":20,
         "outcome_amount":19,"outcome_currency":"trx"}
  raw=json.dumps(valid).encode()
  sig=hmac.new(env["NOWPAYMENTS_IPN_SECRET"].encode(),
     json.dumps(valid,sort_keys=True,separators=(",",":")).encode(),
     hashlib.sha512).hexdigest()
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self,limit):
    return json.dumps(valid).rstrip('}').encode()+b',"payment_status":"finished"}'
  with self.assertRaises(ProviderError):
   verify_processor_payment(payment_id=987,invoice_id=654,
       order_id="MPWF-SECURE1234567",price_usd="4.00",signed_ipn_raw=raw,
       signed_ipn_signature=sig,env=env,opener=lambda req,timeout:Response())

if __name__=="__main__":unittest.main()
