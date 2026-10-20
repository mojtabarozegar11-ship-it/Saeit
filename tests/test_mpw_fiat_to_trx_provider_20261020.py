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

if __name__=="__main__":unittest.main()
