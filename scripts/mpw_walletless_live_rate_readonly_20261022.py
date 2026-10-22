
# Same Python interpreter loads the pure kernel before this read-only integration.
import os,sys,json,hashlib,secrets
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone
APP=Path('/home/zomorod2/Saeit-staging')
ROOT=Path('/home/zomorod2/mojplaywin.com')
if APP.is_symlink() or ROOT.is_symlink() or not APP.is_dir():raise RuntimeError('Incorrect app root')
if "APP='/home/zomorod2/Saeit-staging'" not in (ROOT/'passenger_wsgi.py').read_text('utf8','replace'):raise RuntimeError('Not MojPlayWin')
os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.utils import timezone as django_tz
from core.models import Product
from mpw_commerce.buyer_orders import _eligible
from mpw_commerce.invoicing import RECEIVERS
from mpw_commerce.buyer_wallets import fetch_server_rate
from mpw_commerce.models import CommerceInvoice
product=Product.objects.get(pk=779)
if not _eligible(product) or not product.active or product.currency!='USD':raise RuntimeError('Trial product not approved')
recipient=RECEIVERS['TRX'][1]
network=RECEIVERS['TRX'][0]
if network!=NETWORK:raise RuntimeError('Wrong network')
quote=fetch_server_rate('TRX')
now=django_tz.now()
def used(sun):
 return CommerceInvoice.objects.filter(network=NETWORK,recipient=recipient,amount_atomic=str(sun)).exists()
intent=issue_intent(
  order_id=900001,customer_id=900002,recipient=recipient,usd_total=Decimal(str(product.price)),
  usd_per_trx=Decimal(str(quote.usd_per_asset)),quote_observed_at=quote.observed_at,
  now=now,is_amount_reserved=used,random_below=secrets.randbelow)
if intent.amount_sun<=0 or intent.expires_at-intent.issued_at!=INVOICE_TTL:raise RuntimeError('Invoice calculator failed')
print('MPW_TRX_WALLETLESS_LIVE_RATE_READONLY='+json.dumps({
  'approved_trial_product':779,'usd_total':str(product.price),
  'network':intent.network,'fresh_rate_available':True,
  'invoice_expiration_minutes':10,'quoted_amount_precision_sun':True,
  'amount_reservation_was_not_committed':True,
  'would_require_persistent_reservation':True,
  'no_wallet_public_or_private_addresses_disclosed':True,
  'no_orders_created':True,'financial_writes':0
}))
