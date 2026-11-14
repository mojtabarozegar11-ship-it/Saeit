import unittest
from checkout_trace_auditor import audit_checkout_trace
from checkout_audit_html_report import render_checkout_report
ORDER='a'*64;PAY='b'*64

def event(n,kind,source='client',payment_ref=''):
 return {'event_id':n,'order_ref':ORDER,'event':kind,'source':source,'amount':'10.00','currency':'USD','payment_ref':payment_ref}
def report(events):return audit_checkout_trace({'schema_version':1,'events':events})
class CheckoutReportTests(unittest.TestCase):
 def test_no_unsupported_live_payment_claim(self):
  text=render_checkout_report(report([event('a','checkout_created')]))
  self.assertIn('lang="fa" dir="rtl"',text)
  self.assertIn('اثبات پرداخت',text)
 def test_missing_fulfillment_shown_as_risk(self):
  events=[event('a','checkout_created'),event('b','payment_confirmed','gateway',PAY)]
  self.assertIn('تأیید پرداخت بدون ثبت تحویل',render_checkout_report(report(events)))
 def test_html_safe_long_hashed_ref(self):
  self.assertIn(ORDER,render_checkout_report(report([event('a','checkout_created')])))
 def test_injected_unknown_issue_refused(self):
  r=report([event('a','checkout_created')]);r['orders'][0]['issues']=['<script>alert(1)</script>']
  with self.assertRaisesRegex(ValueError,'unsafe'):render_checkout_report(r)
 def test_wrong_scope_refused(self):
  r=report([event('a','checkout_created')]);r['report_scope']='PAID'
  with self.assertRaises(ValueError):render_checkout_report(r)
if __name__=='__main__':unittest.main()
