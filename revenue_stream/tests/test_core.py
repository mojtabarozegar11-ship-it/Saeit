import concurrent.futures,hashlib,sqlite3,tempfile,unittest
from pathlib import Path
from revenue_stream.core import Store,Rejected,password_valid

class CoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name)/'orders.sqlite3');self.sha='a'*64
 def tearDown(self):self.tmp.cleanup()
 def order(self,nonce='one'):return self.s.create('buyer@example.test','a long test password',1490000,self.sha,nonce,'organic','test-terms')
 def pay(self,o,ref='123'):
  self.s.claim_request(o['id']);a='A'+o['id'];self.s.attach(o['id'],a);self.s.verified(o['id'],a,o['amount'],ref,100);return a
 def test_password_not_plaintext(self):
  o=self.order();self.assertNotEqual(o['password'],'a long test password');self.assertTrue(password_valid('a long test password',o['password']))
 def test_create_idempotent(self):self.assertEqual(self.order()['id'],self.order()['id'])
 def test_order_cannot_change(self):
  o=self.order()
  with self.assertRaises(sqlite3.IntegrityError),self.s.tx() as db:db.execute('UPDATE orders SET amount=1 WHERE id=?',(o['id'],))
 def test_claim_once_concurrently(self):
  o=self.order()
  with concurrent.futures.ThreadPoolExecutor(4) as pool:results=list(pool.map(lambda _:self.s.claim_request(o['id']),range(8)))
  self.assertEqual(sum(results),1)
 def test_no_free_download(self):
  with self.assertRaises(Rejected):self.s.download(self.order()['id'],self.sha)
 def test_mismatched_amount(self):
  o=self.order();self.s.claim_request(o['id']);a='A'+o['id'];self.s.attach(o['id'],a)
  with self.assertRaises(Rejected):self.s.verified(o['id'],a,1,'123',100)
  self.assertEqual(self.s.metrics()['paid_orders'],0)
 def test_reference_required(self):
  o=self.order();self.s.claim_request(o['id']);a='A'+o['id'];self.s.attach(o['id'],a)
  with self.assertRaises(Rejected):self.s.verified(o['id'],a,o['amount'],'',101)
 def test_callback_replay_once(self):
  o=self.order();a=self.pay(o)
  with concurrent.futures.ThreadPoolExecutor(4) as pool:results=list(pool.map(lambda _:self.s.verified(o['id'],a,o['amount'],'123',101),range(8)))
  self.assertEqual(sum(results),0);self.assertEqual(self.s.metrics()['events']['payment_verified'],1)
 def test_ref_cannot_pay_two_orders(self):
  one=self.order();self.pay(one);two=self.order('two')
  with self.assertRaises((Rejected,sqlite3.IntegrityError)):self.pay(two)
  self.assertEqual(self.s.metrics()['paid_orders'],1)
 def test_unknown_request_not_retried(self):
  o=self.order();self.s.claim_request(o['id']);self.s.uncertain(o['id']);self.assertFalse(self.s.claim_request(o['id']))
 def test_download_quota_and_artifact(self):
  o=self.order();self.pay(o)
  with self.assertRaises(Rejected):self.s.download(o['id'],'b'*64)
  for _ in range(20):self.s.download(o['id'],self.sha)
  with self.assertRaises(Rejected):self.s.download(o['id'],self.sha)
 def test_support_feedback_and_reply(self):
  o=self.order();tid=self.s.ticket(o['id'],'support','File does not open on my device');self.s.respond(tid,'Please extract the complete ZIP first.');self.assertEqual(self.s.tickets(o['id'])[0]['state'],'answered')
 def test_refund_accounting_revokes_access(self):
  o=self.order();self.pay(o);self.s.record_external_refund(o['id'],o['amount'],'owner-reviewed-bank-receipt-test')
  self.assertEqual(self.s.metrics()['collected_after_refunds_irr'],0)
  with self.assertRaises(Rejected):self.s.download(o['id'],self.sha)
 def test_rate_and_event_dedupe(self):
  for _ in range(3):self.assertTrue(self.s.rate('test',3))
  self.assertFalse(self.s.rate('test',3));self.s.event('visit','same');self.s.event('visit','same');self.assertEqual(self.s.metrics()['events']['visit'],1)
 def test_no_profit_or_distribution_invention(self):
  o=self.order();self.pay(o);m=self.s.metrics();self.assertIsNone(m['profit']);self.assertIsNone(m['net_distributable_revenue'])
 def test_auth_wrong_order_email_password(self):
  o=self.order();self.assertTrue(self.s.authenticate(o['id'],'buyer@example.test','a long test password'));self.assertFalse(self.s.authenticate(o['id'],'else@example.test','a long test password'));self.assertFalse(self.s.authenticate(o['id'],'buyer@example.test','wrong'))
