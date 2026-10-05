import io,os,tempfile,unittest,zipfile
from unittest.mock import patch
os.environ.setdefault('DJANGO_SETTINGS_MODULE','revenue_stream.test_settings')
import django;django.setup()
from django.test import Client
from revenue_stream import views,config

class FakeGateway:
 # Test double only; never selected by production configuration.
 def create(self,amount,oid,callback):self.amount=amount;return 'A'+oid
 def url(self,authority):return 'https://payment.zarinpal.com/pg/StartPay/'+authority
 def verify(self,authority,amount):return {'code':100,'reference':'123456789'}

class WebTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'ZM_COSTKIT_DATA_DIR':self.tmp.name});self.env.start()
  self.c=Client(enforce_csrf_checks=True,HTTP_HOST='zomorodmelal.ir',HTTP_ORIGIN='https://zomorodmelal.ir');self.fake=FakeGateway()
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def post(self,url,data=None,client=None):
  c=client or self.c
  return c.post(url,data or {},secure=True,HTTP_X_CSRFTOKEN=c.cookies['csrftoken'].value)
 def create_order(self):
  with patch('revenue_stream.views.readiness',return_value=[]):
   self.c.get('/costkit/checkout/',secure=True);nonce=self.c.session['costkit_nonce']
   r=self.post('/costkit/checkout/',{'nonce':nonce,'email':'buyer@example.test','password':'a long test password','password_confirm':'a long test password','accept':'yes','amount':'1'})
  self.assertEqual(r.status_code,302);return r['Location'].split('/')[-2]
 def paid(self):
  oid=self.create_order()
  with patch('revenue_stream.views.readiness',return_value=[]),patch('revenue_stream.views.gateway',return_value=self.fake):
   r=self.post('/costkit/order/'+oid+'/pay/');self.assertEqual(r.status_code,302)
   self.assertEqual(self.fake.amount,1490000)
   r=self.c.get('/costkit/callback/',{'Authority':'A'+oid,'Status':'OK'},secure=True);self.assertEqual(r.status_code,302)
  return oid
 def test_pending_gate_no_order_or_payment(self):
  with patch('revenue_stream.views.gateway') as gateway:
   r=self.c.get('/costkit/checkout/',secure=True);self.assertEqual(r.status_code,503);gateway.assert_not_called()
  self.assertEqual(views.store().metrics()['paid_orders'],0)
 def test_csrf_required(self):
  with patch('revenue_stream.views.readiness',return_value=[]):self.assertEqual(self.c.post('/costkit/checkout/',{},secure=True).status_code,403)
 def test_paid_delivery_valid_zip(self):
  oid=self.paid();r=self.post('/costkit/order/'+oid+'/download/');self.assertEqual(r.status_code,200)
  content=b''.join(r.streaming_content)
  with zipfile.ZipFile(io.BytesIO(content)) as z:self.assertEqual(set(z.namelist()),set(config.PRODUCT_FILES));self.assertIn(b'CostKit',z.read('calc.js'))
 def test_callback_does_not_grant_outsider(self):
  oid=self.paid();other=Client(HTTP_HOST='zomorodmelal.ir')
  r=other.get('/costkit/callback/',{'Authority':'A'+oid,'Status':'OK'},secure=True);self.assertEqual(r.status_code,200)
  self.assertEqual(other.post('/costkit/order/'+oid+'/download/',secure=True).status_code,401)
 def test_bad_provider_does_not_deliver(self):
  oid=self.create_order()
  from revenue_stream.gateway import GatewayError
  with patch('revenue_stream.views.readiness',return_value=[]),patch('revenue_stream.views.gateway',return_value=self.fake):self.post('/costkit/order/'+oid+'/pay/')
  with patch('revenue_stream.views.gateway') as g:
   g.return_value.verify.side_effect=GatewayError('test-timeout')
   r=self.c.get('/costkit/callback/',{'Authority':'A'+oid,'Status':'OK'},secure=True);self.assertEqual(r.status_code,502)
  self.assertEqual(self.post('/costkit/order/'+oid+'/download/').status_code,403)
 def test_nonce_and_acceptance(self):
  with patch('revenue_stream.views.readiness',return_value=[]):
   self.c.get('/costkit/checkout/',secure=True);self.assertEqual(self.post('/costkit/checkout/',{'nonce':'wrong'}).status_code,400)
 def test_buyer_relogin_and_logout(self):
  oid=self.paid();self.post('/costkit/logout/');self.assertEqual(self.c.get('/costkit/order/'+oid+'/',secure=True).status_code,302)
  self.c.get('/costkit/access/',secure=True)
  r=self.post('/costkit/access/',{'order':oid,'email':'buyer@example.test','password':'a long test password'});self.assertEqual(r.status_code,302)
  self.assertEqual(self.c.get('/costkit/order/'+oid+'/',secure=True).status_code,200)
 def test_support_survives_and_escapes_html(self):
  oid=self.paid();self.post('/costkit/order/'+oid+'/ticket/',{'kind':'feedback','body':'<script>alert(1)</script> Helpful tool'})
  r=self.c.get('/costkit/order/'+oid+'/',secure=True);self.assertNotIn(b'<script>alert',r.content);self.assertIn(b'&lt;script&gt;',r.content)
 def test_legacy_owner_identity_required(self):self.assertEqual(self.c.get('/costkit/owner/',secure=True).status_code,403)
 def test_private_routes_not_cacheable(self):
  r=self.c.get('/costkit/access/',secure=True);self.assertEqual(r['Cache-Control'],'no-store, private');self.assertIn('noindex',r['X-Robots-Tag'])
 def test_price_snapshot_and_archive(self):
  oid=self.paid();old=views.store().get(oid)['artifact']
  with patch('revenue_stream.config.package',return_value=b'new-version'):
   r=self.post('/costkit/order/'+oid+'/download/');self.assertEqual(r.status_code,200);self.assertGreater(len(b''.join(r.streaming_content)),100)
  self.assertEqual(views.store().get(oid)['artifact'],old)
 def test_unknown_asset_and_path_traversal(self):self.assertEqual(self.c.get('/costkit/assets/core.py/',secure=True).status_code,404)
 def test_no_live_credentials_in_artifact(self):
  content=config.package()
  with zipfile.ZipFile(io.BytesIO(content)) as z:
   for n in z.namelist():self.assertNotIn(b'ZARINPAL_MERCHANT_ID',z.read(n));self.assertNotIn(b'DJANGO_SECRET_KEY',z.read(n))
